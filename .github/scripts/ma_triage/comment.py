"""Render and upsert the single "sticky" triage comment.

The bot keeps exactly one comment per issue, found via a hidden marker. A small
JSON blob is embedded in an HTML comment so subsequent runs can recover what the
bot previously did (reminder stage, whether a Copilot task was dispatched, …)
without needing any external state store.

All diagnostics-derived text routed through here is already sanitized by the
callers (see :mod:`ma_triage.sanitize`); this module additionally never
interpolates untrusted values into the state block.
"""

from __future__ import annotations

import json
from typing import Any

from . import config
from .gh import GitHubClient
from .models import RagResult, Severity, TriageResult
from .sanitize import fenced, inline

_SEVERITY_ICON = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟠",
    Severity.INFO: "🔵",
}

_DIAGNOSTICS_HOWTO = (
    "On Music Assistant **2.10 or newer**, grab it from **Settings → Download "
    "diagnostics** and attach the `music-assistant-diagnostics-*.json` file. On "
    "**2.9.6–2.9.x** you can open `/diagnostics?include_log_tail=true` and save "
    "the JSON. On **older versions** (no diagnostics feature yet), attach your "
    "**server log file** instead. Diagnostics are privacy-sanitized (paths, "
    "tokens, emails and non-local IPs are removed) and let us understand your "
    "setup at a glance."
)


# --------------------------------------------------------------------------- #
# State (hidden JSON) helpers
# --------------------------------------------------------------------------- #
def parse_state(body: str | None) -> dict[str, Any]:
    """Extract the embedded state JSON from an existing comment body."""
    if not body or config.STATE_BEGIN not in body:
        return {}
    try:
        start = body.index(config.STATE_BEGIN) + len(config.STATE_BEGIN)
        end = body.index(config.STATE_END, start)
        return json.loads(body[start:end].strip())
    except (ValueError, json.JSONDecodeError):
        return {}


def _render_state(state: dict[str, Any]) -> str:
    # Compact, and guaranteed HTML-comment-safe (json escapes < > & as unicode).
    blob = json.dumps(state, separators=(",", ":"), default=str)
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e")
    return f"{config.STATE_BEGIN}{blob}{config.STATE_END}"


def find_sticky(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the bot's existing sticky comment, if any."""
    for comment in comments:
        if config.STICKY_MARKER in (comment.get("body") or ""):
            return comment
    return None


# --------------------------------------------------------------------------- #
# Body builders
# --------------------------------------------------------------------------- #
def _source_noun(result: TriageResult) -> str:
    """"diagnostics" or "log", matching what we actually parsed."""
    diag = result.diagnostics
    if diag is not None and diag.source == "log":
        return "log"
    return "diagnostics"


def _findings_section(result: TriageResult) -> str:
    noun = _source_noun(result)
    if not result.findings:
        return (
            f"I went through the attached {noun} and didn't spot any obvious "
            "problems in the automated checks. A maintainer will take a closer "
            "look."
        )
    parts = [f"Here's what I found in the attached {noun}:\n"]
    for finding in result.findings:
        icon = _SEVERITY_ICON.get(finding.severity, "•")
        parts.append(f"{icon} **{finding.title}**\n\n{finding.detail}\n")
    return "\n".join(parts)


def _ai_section(result: TriageResult) -> str:
    ai = result.ai
    if ai is None:
        return ""
    lines = ["\n### 🤖 AI assessment\n"]
    if ai.summary:
        lines.append(inline(ai.summary, max_len=1000))
    if ai.likely_root_cause:
        lines.append(f"\n**Likely cause:** {inline(ai.likely_root_cause, max_len=1000)}")
    meta = []
    if ai.category:
        meta.append(f"category: `{inline(ai.category, max_len=40)}`")
    if ai.confidence is not None:
        meta.append(f"confidence: {ai.confidence:.0%}")
    if ai.possibly_fixed_in_version:
        meta.append(f"possibly fixed in: `{inline(ai.possibly_fixed_in_version, max_len=40)}`")
    if meta:
        lines.append("\n_" + " · ".join(meta) + "_")
    return "\n".join(lines)


def _system_summary(result: TriageResult) -> str:
    diag = result.diagnostics
    if diag is None:
        return ""
    sys = diag.system
    bits = []
    if sys.version:
        bits.append(f"**Version:** {inline(sys.version)}")
    elif result.reported_version:
        bits.append(f"**Version:** {inline(result.reported_version)}")
    if sys.hass_addon is not None:
        bits.append(f"**Install:** {'HA add-on' if sys.hass_addon else 'standalone'}")
    elif result.install_method:
        bits.append(f"**Install:** {inline(result.install_method, max_len=60)}")
    if sys.python_version:
        bits.append(f"**Python:** {inline(sys.python_version)}")
    if sys.platform:
        bits.append(f"**Platform:** {inline(sys.platform)}")
    players = diag.players.get("total") if isinstance(diag.players, dict) else None
    if isinstance(players, int):
        bits.append(f"**Players:** {players}")
    if not bits:
        return ""
    return " · ".join(bits)


def _frontend_body(result: TriageResult) -> list[str]:
    """Missing-info request for a frontend/UI bug report."""
    parts: list[str] = []
    if result.missing_sections:
        pretty = ", ".join(f"**{s}**" for s in result.missing_sections)
        parts.append(
            f"To help us look into this UI issue, could you fill in the "
            f"following section(s): {pretty}?\n"
        )
    if result.missing_attachment:
        parts.append(config.FRONTEND_MISSING_MESSAGE)
    return parts


def _missing_sections_line(result: TriageResult) -> str:
    """A gentle request for empty required sections (main form)."""
    if result.form_kind != "main" or not result.missing_sections:
        return ""
    pretty = ", ".join(f"**{s}**" for s in result.missing_sections)
    return (
        f"One thing to help us dig in: the following required section(s) look "
        f"empty — {pretty}. Could you fill them in?"
    )


def _doc_link(label: str, url: str) -> str:
    """A sanitized markdown bullet link to a docs page.

    Doc content is from the public docs repo (comparatively trusted) but is still
    sanitized before echoing; the URL is derived from our own config + slug.
    """
    return f"- [{inline(label, max_len=160) or url}]({url})"


def _rag_section(result: TriageResult) -> str:
    """Render the optional docs-answer + related-posts sections.

    Returns ``""`` when the RAG layer produced nothing (or is disabled), so the
    comment is byte-identical to Phase 1 in that case.
    """
    rag: RagResult | None = result.rag
    if rag is None or not rag.has_output:
        return ""
    parts: list[str] = []

    if rag.tier == "high" and rag.doc_answer is not None:
        parts.append(config.DOCS_ANSWER_HEADING)
        # The answer is model-generated and grounded in the cited docs; sanitize
        # it anyway so it can never ping users or break out of the comment.
        parts.append(fenced(rag.doc_answer.answer, max_len=config.MAX_DOC_ANSWER_CHARS))
        if rag.cited_chunks:
            parts.append("\n**Sources:**")
            for chunk in rag.cited_chunks:
                parts.append(_doc_link(chunk.label, chunk.url))
        parts.append("\n" + config.DOCS_ANSWER_DISCLAIMER)
    elif rag.tier == "medium" and rag.doc_hits:
        parts.append(config.DOCS_LINKS_HEADING)
        parts.append("These documentation pages look related to your report:")
        for hit in rag.doc_hits[: config.DOCS_LINKS_SHOWN]:
            parts.append(_doc_link(hit.chunk.label, hit.chunk.url))
        parts.append("\n" + config.DOCS_ANSWER_DISCLAIMER)

    if rag.related_posts:
        parts.append("\n" + config.RELATED_POSTS_HEADING)
        parts.append(config.RELATED_POSTS_INTRO)
        for post in rag.related_posts:
            closed = " _(closed)_" if post.state == "closed" else ""
            title = inline(post.title, max_len=140)
            parts.append(f"- [#{post.number}: {title}]({post.url}){closed}")

    return "\n".join(parts)


def build_body(result: TriageResult) -> str:
    """Render the full sticky-comment body for a triage pass."""
    parts = [config.STICKY_MARKER, "", config.GREETING, ""]

    if result.form_kind == "frontend":
        parts.extend(_frontend_body(result))
    elif result.is_actionable:
        if result.diagnostics is not None and result.diagnostics.source == "log":
            parts.append(config.LOG_FALLBACK_NOTE)
            parts.append("")
        summary = _system_summary(result)
        if summary:
            parts.append(summary)
            parts.append("")
        parts.append(_findings_section(result))
        ai = _ai_section(result)
        if ai:
            parts.append(ai)
        # Even with usable diagnostics, still ask for any empty required sections.
        missing = _missing_sections_line(result)
        if missing:
            parts.append("\n" + missing)
    elif result.diagnostics_invalid:
        parts.append(
            "Thanks for attaching a file! Unfortunately I couldn't read it — it "
            "may be truncated, from an incompatible version, or not the right "
            "file. Could you regenerate and re-attach it?\n\n" + _DIAGNOSTICS_HOWTO
        )
    else:
        # Main form, no usable attachment.
        if result.missing_sections:
            pretty = ", ".join(f"**{s}**" for s in result.missing_sections)
            parts.append(
                f"To help us look into this, could you fill in the following "
                f"section(s) of the report: {pretty}?\n"
            )
        if result.has_media_attachment:
            # Reporter pasted a screenshot/image instead of the actual file.
            parts.append(config.SCREENSHOT_ATTACHMENT_NOTE + " " + _DIAGNOSTICS_HOWTO)
        else:
            lead = (
                "It would also really help if you could attach"
                if result.missing_sections
                else "Could you attach"
            )
            parts.append(
                f"{lead} a **diagnostics report or log file**? " + _DIAGNOSTICS_HOWTO
            )
        # Even without a file we can still nudge on an outdated version, etc.
        if result.findings:
            parts.append("")
            parts.append(_findings_section(result))

    if result.log_wall_detected:
        parts.append(
            "\n> 💡 It looks like a large log was pasted directly into the issue. "
            "A diagnostics report (or a log attached as a file) is much easier for "
            "us to work with than inline logs."
        )

    rag_section = _rag_section(result)
    if rag_section:
        parts.append("")
        parts.append(rag_section)

    if result.maintainers_to_ping:
        pings = " ".join(f"@{m}" for m in sorted(result.maintainers_to_ping))
        parts.append(f"\nHeads-up {pings} — this looks like it may be your area. 🙇")

    parts.append(config.DISCLOSURE_FOOTER)
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Upsert
# --------------------------------------------------------------------------- #
def upsert(
    gh: GitHubClient,
    number: int,
    body: str,
    state: dict[str, Any],
    *,
    comments: list[dict[str, Any]] | None = None,
) -> None:
    """Create or update the single sticky comment, embedding ``state``."""
    full = f"{body}\n\n{_render_state(state)}"
    if comments is None:
        comments = gh.list_comments(number)
    existing = find_sticky(comments)
    if existing:
        gh.update_comment(existing["id"], full)
    else:
        gh.create_comment(number, full)
