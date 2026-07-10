"""Issue-template parsing, per-form completeness checks and log-wall detection.

GitHub issue *forms* render each field label as a ``### <label>`` heading followed
by the reporter's answer. We branch behaviour by *form kind* (detected from the
issue's labels) and validate the required sections for that specific form.

Section headers are kept in sync with ``.github/ISSUE_TEMPLATE/*.yml``:

* ``bug_report.yml``            → main server bug form   (label ``triage``)
* ``frontend_bug_report.yml``   → frontend/UI bug form   (labels ``triage``,
  ``frontend``)
* ``translation_contribute.yml``→ translation form       (labels ``triage``,
  ``translation``) — triage is skipped entirely for these.
"""

from __future__ import annotations

import re

from . import config

# --------------------------------------------------------------------------- #
# Section headers (must match the issue forms exactly)
# --------------------------------------------------------------------------- #
SECTION_WHAT_HAPPENED = "What happened?"
SECTION_HOW_TO_REPRODUCE = "How to reproduce"
SECTION_VERSION = "Music Assistant version"
SECTION_INSTALL_METHOD = "How do you run Music Assistant?"
SECTION_DIAGNOSTICS = "Diagnostics report or log file"
SECTION_ANYTHING_ELSE = "Anything else?"
SECTION_BROWSER_OS = "Browser and operating system"
SECTION_SCREENSHOT = "Screenshot or recording"

# Required *text* sections per form (the attachment fields are validated
# separately via attachments.py, since their content is a URL/upload).
REQUIRED_SECTIONS_MAIN = (
    SECTION_WHAT_HAPPENED,
    SECTION_HOW_TO_REPRODUCE,
    SECTION_VERSION,
    SECTION_INSTALL_METHOD,
)
REQUIRED_SECTIONS_FRONTEND = (
    SECTION_VERSION,
    SECTION_BROWSER_OS,
    SECTION_WHAT_HAPPENED,
    SECTION_HOW_TO_REPRODUCE,
)

# Free-text sections scanned for provider mentions (main form). The old
# "Affected provider(s)" field was fully removed from the form (support #5808);
# the "What happened?" hint now asks reporters to name the provider/player in
# prose, so the free-text scan below keeps its signal.
PROVIDER_SCAN_SECTIONS = (
    SECTION_WHAT_HAPPENED,
    SECTION_HOW_TO_REPRODUCE,
    SECTION_ANYTHING_ELSE,
)

_RE_SECTION = re.compile(r"^###\s+(.*?)\s*$")
# A line that looks like a log line: has a level keyword or an ISO-ish timestamp.
_RE_LOG_LINE = re.compile(
    r"(?:\b(?:CRITICAL|ERROR|WARNING|WARN|INFO|DEBUG)\b)"
    r"|(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})"
)
_RE_FENCE = re.compile(r"```")


def form_kind(labels: set[str] | list[str] | None) -> str:
    """Classify the issue form from its labels.

    Returns ``"translation"``, ``"frontend"`` or ``"main"``. Matching is
    case-insensitive and tolerant of extra labels.
    """
    names = {str(name).strip().lower() for name in (labels or [])}
    if config.LABEL_TRANSLATION.lower() in names:
        return "translation"
    if config.LABEL_FRONTEND.lower() in names:
        return "frontend"
    return "main"


def parse_sections(body: str | None) -> dict[str, str]:
    """Split an issue body into ``{section_heading: content}``."""
    if not body:
        return {}
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in body.splitlines():
        match = _RE_SECTION.match(line)
        if match:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = match.group(1).strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def _is_empty(content: str | None) -> bool:
    """True when a section is blank or the form's ``_No response_`` sentinel."""
    text = (content or "").strip()
    if not text:
        return True
    return text == config.NO_RESPONSE_SENTINEL


def section_value(body: str | None, name: str) -> str | None:
    """Return a section's content, or ``None`` if absent/empty/``_No response_``."""
    value = parse_sections(body).get(name)
    return None if _is_empty(value) else value.strip()


def required_sections_for(kind: str) -> tuple[str, ...]:
    if kind == "frontend":
        return REQUIRED_SECTIONS_FRONTEND
    return REQUIRED_SECTIONS_MAIN


def missing_sections(body: str | None, kind: str = "main") -> list[str]:
    """Required sections (for the given form) that are absent or empty."""
    sections = parse_sections(body)
    missing: list[str] = []
    for name in required_sections_for(kind):
        if _is_empty(sections.get(name)):
            missing.append(name)
    return missing


def extract_version(body: str | None) -> str | None:
    """Reporter-entered value of the "Music Assistant version" field."""
    return section_value(body, SECTION_VERSION)


def extract_install_method(body: str | None) -> str | None:
    """Reporter-selected value of "How do you run Music Assistant?"."""
    return section_value(body, SECTION_INSTALL_METHOD)


def provider_scan_text(body: str | None, title: str | None = None) -> str:
    """Concatenate the fields worth scanning for provider mentions."""
    sections = parse_sections(body)
    parts: list[str] = []
    if title:
        parts.append(title)
    for name in PROVIDER_SCAN_SECTIONS:
        value = sections.get(name)
        if not _is_empty(value):
            parts.append(value)
    return "\n".join(parts)


def detect_log_wall(body: str | None) -> bool:
    """True when the body contains a large pasted log (vs. an attached file).

    Triggers on either a long fenced code block or many consecutive log-looking
    lines. Used to gently ask the reporter to attach the file instead.
    """
    if not body:
        return False

    # Count log-looking lines overall.
    log_lines = sum(1 for line in body.splitlines() if _RE_LOG_LINE.search(line))
    if log_lines >= config.MAX_LOG_WALL_LINES:
        return True

    # Also catch a single very long fenced block.
    if _RE_FENCE.search(body):
        in_fence = False
        block: list[str] = []
        for line in body.splitlines():
            if _RE_FENCE.search(line):
                if in_fence and len(block) >= config.MAX_LOG_WALL_LINES:
                    return True
                in_fence = not in_fence
                block = []
            elif in_fence:
                block.append(line)
    return False
