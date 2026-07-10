"""Issue-template completeness checks and "wall of log" detection.

The bug-report template renders as ``### Section\n\n<value>`` blocks. We check
that the important sections are filled in, and detect when a reporter pasted a
large log directly into the issue instead of attaching the file.

``REQUIRED_SECTIONS`` must be kept in sync with ``.github/ISSUE_TEMPLATE`` (the
template is being reworked to request the diagnostics file).
"""

from __future__ import annotations

import re

from . import config

# Section headings that must be present and non-empty. Keep in sync with the
# issue form. Kept intentionally small/robust so template tweaks don't cause
# false "missing section" nags.
REQUIRED_SECTIONS = (
    "The problem",
    "How to reproduce",
)

# Placeholder fragments that indicate a section was left untouched.
_PLACEHOLDERS = (
    "DO NOT PASTE",
    "For Audiobookshelf include broken book ASINs here",
)

_RE_SECTION = re.compile(r"^###\s+(.*?)\s*$")
# A line that looks like a log line: has a level keyword or an ISO-ish timestamp.
_RE_LOG_LINE = re.compile(
    r"(?:\b(?:CRITICAL|ERROR|WARNING|WARN|INFO|DEBUG)\b)"
    r"|(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})"
)
_RE_FENCE = re.compile(r"```")


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


def missing_sections(body: str | None) -> list[str]:
    """Return required sections that are absent, empty, or placeholder-only."""
    sections = parse_sections(body)
    missing: list[str] = []
    for name in REQUIRED_SECTIONS:
        content = sections.get(name, "").strip()
        if not content or _is_placeholder(content):
            missing.append(name)
    return missing


def _is_placeholder(content: str) -> bool:
    if len(content) > 100:
        return False
    return any(p in content for p in _PLACEHOLDERS)


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
