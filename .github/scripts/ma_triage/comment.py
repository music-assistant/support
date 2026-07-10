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
from .models import Severity, TriageResult
from .sanitize import inline

_SEVERITY_ICON = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟠",
    Severity.INFO: "🔵",
}

_DIAGNOSTICS_HOWTO = (
    "You can grab it in the Music Assistant UI: **Settings → Download "
    "diagnostics**. The file is privacy-sanitized (paths, tokens, emails and "
    "non-local IPs are removed) and helps us understand your setup at a glance. "
    "Please attach the `music-assistant-diagnostics-*.json` file to this issue."
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
def _findings_section(result: TriageResult) -> str:
    if not result.findings:
        return (
            "I went through the attached diagnostics and didn't spot any obvious "
            "problems in the automated checks. A maintainer will take a closer "
            "look."
        )
    parts = ["Here's what I found in the attached diagnostics:\n"]
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
    if sys.hass_addon is not None:
        bits.append(f"**Install:** {'HA add-on' if sys.hass_addon else 'standalone'}")
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


def build_body(result: TriageResult) -> str:
    """Render the full sticky-comment body for a triage pass."""
    parts = [config.STICKY_MARKER, "", config.GREETING, ""]

    if result.is_actionable:
        summary = _system_summary(result)
        if summary:
            parts.append(summary)
            parts.append("")
        parts.append(_findings_section(result))
        ai = _ai_section(result)
        if ai:
            parts.append(ai)
    elif result.diagnostics_invalid:
        parts.append(
            "Thanks for attaching a diagnostics file! Unfortunately I couldn't "
            "read it — it may be truncated, from an incompatible version, or not "
            "the right file. Could you regenerate and re-attach it?\n\n"
            + _DIAGNOSTICS_HOWTO
        )
    else:
        # No diagnostics attached.
        if result.missing_sections:
            pretty = ", ".join(f"**{s}**" for s in result.missing_sections)
            parts.append(
                f"To help us look into this, could you fill in the following "
                f"section(s) of the report: {pretty}?\n"
            )
        parts.append(
            "It would also really help if you could attach a **diagnostics "
            "file**. " + _DIAGNOSTICS_HOWTO
        )

    if result.log_wall_detected:
        parts.append(
            "\n> 💡 It looks like a large log was pasted directly into the issue. "
            "A diagnostics file (or a log attached as a file) is much easier for "
            "us to work with than inline logs."
        )

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
