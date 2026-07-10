"""Neutralise untrusted, diagnostics-derived strings before echoing them.

Even though the diagnostics file is sanitized server-side, a reporter could
attach a hand-crafted file. Anything from the file (provider names, error
messages, tracebacks) is therefore treated as hostile when we render it into a
GitHub comment, to prevent:
* pinging arbitrary users via ``@mention``,
* breaking out of code spans / fences,
* injecting HTML or faking our hidden state markers,
* auto-linking arbitrary URLs.
"""

from __future__ import annotations

from . import config

_ZERO_WIDTH = "\u200b"


def _common(value: str, max_len: int) -> str:
    # Escape HTML-sensitive characters (also defeats fake <!-- --> markers).
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Defuse @mentions and #refs so they can't ping people or cross-link issues.
    value = value.replace("@", "@" + _ZERO_WIDTH).replace("#", "#" + _ZERO_WIDTH)
    if len(value) > max_len:
        value = value[:max_len] + " …[truncated]"
    return value


def inline(value: str | None, max_len: int = config.MAX_STRING_ECHO) -> str:
    """Sanitise a value for inline use (single line, no code-span breakage)."""
    if not value:
        return ""
    value = " ".join(str(value).split())  # collapse all whitespace/newlines
    value = value.replace("`", "'")  # can't break out of a code span
    return _common(value, max_len)


def fenced(value: str | None, max_len: int = config.MAX_STRING_ECHO * 4) -> str:
    """Sanitise multi-line content for use inside a ``` fenced block."""
    if not value:
        return ""
    value = str(value).replace("`", "'")  # can't break out of the fence
    return _common(value, max_len)
