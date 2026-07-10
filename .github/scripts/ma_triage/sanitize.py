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

import re

from . import config

_ZERO_WIDTH = "\u200b"
_RE_URL_SCHEME = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]{1,31}):(?=//)"
)
_RE_MAILTO = re.compile(r"(?i)\b(mailto):")
_RE_WWW = re.compile(r"(?i)\b(www)(?=\.)")


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


def _escape_markdown_brackets(value: str) -> str:
    """Escape link-label delimiters without a preceding backslash undoing it."""
    return (
        value.replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def link_label(
    value: str | None, max_len: int = config.MAX_STRING_ECHO
) -> str:
    """Sanitise untrusted text used inside a Markdown link label."""
    return _escape_markdown_brackets(inline(value, max_len=max_len))


def markdown_safe(
    value: str | None, max_len: int = config.MAX_STRING_ECHO * 4
) -> str:
    """Sanitise multi-line prose rendered directly as Markdown.

    In addition to the common mention/HTML/fence protections, link/image syntax
    is escaped and URL schemes are broken so model-influenced prose cannot make
    the trusted bot publish an arbitrary clickable link. Deliberate trusted
    citations are rendered separately by the caller.
    """
    if not value:
        return ""
    value = str(value).replace("`", "'")
    value = _common(value, max_len)
    value = _escape_markdown_brackets(value)
    value = _RE_URL_SCHEME.sub(r"\1:" + _ZERO_WIDTH, value)
    value = _RE_MAILTO.sub(r"\1:" + _ZERO_WIDTH, value)
    return _RE_WWW.sub(r"\1" + _ZERO_WIDTH, value)
