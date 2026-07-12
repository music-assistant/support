"""Render and upsert the single "sticky" triage comment.

The bot keeps exactly one comment per issue, found via a hidden marker. A small
JSON blob is embedded in an HTML comment so subsequent runs can recover what the
bot previously did (reminder stage, prior findings, …) without needing any
external state store.

All diagnostics-derived text routed through here is already sanitized by the
callers (see :mod:`ma_triage.sanitize`); this module additionally never
interpolates untrusted values into the state block.
"""

from __future__ import annotations

import json
from typing import Any

from . import config
from .gh import GitHubClient, summary
from .models import RagResult, RelatedPost, Severity, TriageResult
from .sanitize import inline, link_label, markdown_safe

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


def _author_login(comment: dict[str, Any]) -> str:
    actor = comment.get("user") or comment.get("author") or {}
    return str(actor.get("login") or "").lower() if isinstance(actor, dict) else ""


def _owned_sticky(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Sticky authored by the current App (or legacy behaviour when unset)."""
    if not config.BOT_LOGIN:
        return find_sticky(comments)
    login = config.BOT_LOGIN.lower()
    return find_sticky([comment for comment in comments if _author_login(comment) == login])


def _legacy_sticky(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    logins = {login.lower() for login in config.LEGACY_BOT_LOGINS}
    return find_sticky(
        [comment for comment in comments if _author_login(comment) in logins]
    )


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
    inner: list[str] = []
    if ai.summary:
        inner.append(markdown_safe(ai.summary, max_len=1000))
    if ai.likely_root_cause:
        inner.append(
            "\n**Likely cause:** "
            + markdown_safe(ai.likely_root_cause, max_len=1000)
        )
    if ai.evidence:
        inner.append("\n**Evidence considered:**")
        inner.extend(
            f"- {markdown_safe(item, max_len=500)}"
            for item in ai.evidence[:5]
        )
    if ai.maintainer_next_step:
        inner.append(
            "\n**Maintainer next step:** "
            + markdown_safe(ai.maintainer_next_step, max_len=800)
        )
    meta = []
    if ai.category:
        meta.append(f"category: `{inline(ai.category, max_len=40)}`")
    if ai.confidence is not None:
        meta.append(f"confidence: {ai.confidence:.0%}")
    if ai.possibly_fixed_in_version:
        meta.append(f"possibly fixed in: `{inline(ai.possibly_fixed_in_version, max_len=40)}`")
    if meta:
        inner.append("\n_" + " · ".join(meta) + "_")
    if not inner:
        return ""
    # Rendered collapsed: it's an AI hypothesis for a maintainer to sanity-check,
    # not a conclusion shown front-and-centre to the reporter.
    body = "\n".join(inner)
    return (
        "\n<details>\n"
        "<summary>🤖 AI assessment — possible root cause (for maintainers; may be "
        "wrong)</summary>\n\n"
        f"{body}\n"
        "</details>"
    )


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
    return f"- [{link_label(label, max_len=160) or url}]({url})"


def _post_link(post: RelatedPost) -> str:
    closed = " _(closed)_" if post.state == "closed" else ""
    title = link_label(post.title, max_len=140)
    return f"- [#{post.number}: {title}]({post.url}){closed}"


def _provider_docs_section(result: TriageResult) -> str:
    if not result.provider_docs:
        return ""
    parts = [config.PROVIDER_DOCS_HEADING]
    for doc in result.provider_docs:
        parts.append(_doc_link(doc.name, doc.url))
    return "\n".join(parts)


def _render_rag(rag: RagResult | None) -> str:
    """Render the optional docs-answer + related-posts sections.

    Returns ``""`` when the RAG layer produced nothing (or is disabled), so the
    issue comment is byte-identical to Phase 1 in that case. Shared by the issue
    comment and the discussion comment.
    """
    if rag is None or not rag.has_output:
        return ""
    parts: list[str] = []

    if rag.tier == "high" and rag.doc_answer is not None:
        parts.append(config.DOCS_ANSWER_HEADING)
        # The answer is model-generated and grounded in the cited docs; sanitize
        # it anyway so it can never ping users or break out of the comment.
        parts.append(
            markdown_safe(
                rag.doc_answer.answer, max_len=config.MAX_DOC_ANSWER_CHARS
            )
        )
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

    if rag.pinned_posts:
        parts.append("\n" + config.PINNED_POSTS_HEADING)
        parts.append(config.PINNED_POSTS_INTRO)
        parts.extend(_post_link(post) for post in rag.pinned_posts)

    if rag.related_posts:
        if max(post.score for post in rag.related_posts) >= config.RELATED_EXPAND_SCORE:
            parts.append("\n" + config.RELATED_POSTS_HEADING)
            parts.append(config.RELATED_POSTS_INTRO)
            parts.extend(_post_link(post) for post in rag.related_posts)
        else:
            weak = [
                "<details>",
                f"<summary>{config.RELATED_POSTS_WEAK_SUMMARY}</summary>",
                "",
                config.RELATED_POSTS_WEAK_INTRO,
                "",
            ]
            weak.extend(_post_link(post) for post in rag.related_posts)
            weak.extend(["", "</details>"])
            parts.append("\n" + "\n".join(weak))

    return "\n".join(parts)


def _rag_section(result: TriageResult) -> str:
    return _render_rag(result.rag)


def build_discussion_body(rag: RagResult, *, title: str = "") -> str:
    """Render the sticky comment for a Discussion.

    Discussions have no diagnostics, template or labels — the body is purely the
    RAG output (a docs-grounded answer and/or related past posts) wrapped in the
    standard greeting + disclosure footer. Callers only invoke this when
    ``rag.has_output`` is true.
    """
    parts = [config.STICKY_MARKER, "", config.DISCUSSION_GREETING, ""]
    section = _render_rag(rag)
    if section:
        parts.append(section)
    parts.append(config.DISCLOSURE_FOOTER)
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

    provider_docs = _provider_docs_section(result)
    if provider_docs:
        parts.append("")
        parts.append(provider_docs)

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
    existing = _owned_sticky(comments)
    if existing:
        gh.update_comment(existing["id"], full)
    elif config.BOT_LOGIN and _legacy_sticky(comments):
        summary(
            f"#{number}: existing github-actions sticky left unchanged during "
            "GitHub App rollout."
        )
    else:
        gh.create_comment(number, full)


def upsert_discussion(
    gh: GitHubClient,
    discussion_id: str,
    body: str,
    state: dict[str, Any],
    *,
    comments: list[dict[str, Any]],
) -> None:
    """Create or update the single sticky comment on a Discussion (GraphQL).

    ``comments`` are the discussion's existing comment nodes. Only comments the
    current App authored are updated; a legacy github-actions sticky is preserved,
    while a user-forged marker is ignored and cannot block the App's own sticky.
    """
    full = f"{body}\n\n{_render_state(state)}"
    owned = [
        c
        for c in comments
        if c.get("viewerDidAuthor")
        or (
            config.BOT_LOGIN
            and _author_login(c) == config.BOT_LOGIN.lower()
        )
    ]
    existing = find_sticky(owned)
    if existing:
        gh.update_discussion_comment(existing["id"], full)
    elif config.BOT_LOGIN and _legacy_sticky(comments):
        summary(
            "Existing github-actions discussion sticky left unchanged during "
            "GitHub App rollout."
        )
    else:
        gh.add_discussion_comment(discussion_id, full)
