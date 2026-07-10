"""Raw-log fallback: reconstruct a :class:`Diagnostics` from an attached log.

Reporters on Music Assistant versions **older than the diagnostics feature**
(pre-2.9.6) attach a raw ``*.log``/``*.txt`` instead of a diagnostics report.
Unlike the server-produced JSON, a raw log is **not** sanitized, so it may leak
tokens, home directories, IPs, emails and MAC addresses.

This module therefore **redacts first** (mirroring the server's sanitizer) and
only then extracts the subset of facts a log can yield — version banner,
safe-mode, provider setup errors and exception tracebacks grouped by fingerprint
with counts — returning a ``Diagnostics(source="log")`` so the same
analyze/label/comment pipeline runs. Only *derived facts* and *redacted* snippets
ever reach a comment.
"""

from __future__ import annotations

import ipaddress
import re

from .models import Diagnostics, ExceptionEntry, ProviderEntry, SystemInfo

# --------------------------------------------------------------------------- #
# Redaction (runs before anything else)
# --------------------------------------------------------------------------- #
_REDACTED = "<redacted>"

# key=value / key: value secrets (tokens, passwords, api keys, …). The value
# charset includes base64 / url-safe characters (+ / = ~) so tokens like
# "abcd/efgh+ijkl==" are redacted in full rather than truncated at the slash.
_RE_SECRET_KV = re.compile(
    r"(?i)\b(authorization|auth|api[_-]?key|apikey|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|token|password|passwd|pwd|secret)"
    r"(\s*[:=]\s*|\s+)"
    r"(?:bearer\s+)?"
    r"['\"]?[A-Za-z0-9._\-+/=~]{4,}['\"]?"
)
_RE_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{4,}")
# JWT-ish / long opaque tokens.
_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9._\-]{10,}")
# Credentials embedded in a URL: scheme://user:pass@host. Lengths are bounded so
# a long run of scheme/userinfo-valid characters can't cause O(n^2) backtracking.
_RE_URL_CREDS = re.compile(
    r"(?i)\b([a-z][a-z0-9+.\-]{0,15}://)[^\s/:@]{1,256}:[^\s/@]{1,256}@"
)
# Query-string credentials, e.g. ?token=... or &sig=...
_RE_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:token|sig|signature|key|api_key|password|auth)=)[^&\s\"']+"
)
_RE_HOME_UNIX = re.compile(r"/(?:home|Users)/[^/\s\"']+")
_RE_HOME_WIN = re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s\"']+")
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_RE_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# IPv6 candidate: 3-8 colon-separated hex groups. Bounded quantifiers only (no
# catastrophic backtracking); every candidate is validated via ipaddress below,
# so timestamps like "12:00:00" and MAC placeholders are left untouched.
_RE_IPV6 = re.compile(
    r"(?<![\w:.])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![\w:.])"
)


def _redact_ip(match: re.Match[str]) -> str:
    text = match.group(0)
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return text
    # Keep private / loopback / link-local addresses (useful, not sensitive).
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        return text
    return "<redacted-ip>"


def _redact_ipv6(match: re.Match[str]) -> str:
    text = match.group(0)
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return text  # not actually an IPv6 address (e.g. a timestamp)
    if ip.version != 6:
        return text
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        return text
    return "<redacted-ip>"


def redact(text: str) -> str:
    """Strip secrets/PII from raw log text before any of it is used or echoed."""
    text = _RE_URL_CREDS.sub(rf"\1{_REDACTED}@", text)
    text = _RE_QUERY_SECRET.sub(rf"\1{_REDACTED}", text)
    text = _RE_SECRET_KV.sub(rf"\1\2{_REDACTED}", text)
    text = _RE_BEARER.sub(f"Bearer {_REDACTED}", text)
    text = _RE_JWT.sub(_REDACTED, text)
    text = _RE_HOME_UNIX.sub("/home/<redacted>", text)
    text = _RE_HOME_WIN.sub(r"C:\\Users\\<redacted>", text)
    text = _RE_EMAIL.sub("<redacted-email>", text)
    text = _RE_MAC.sub("<redacted-mac>", text)
    text = _RE_IPV4.sub(_redact_ip, text)
    text = _RE_IPV6.sub(_redact_ipv6, text)
    return text


# --------------------------------------------------------------------------- #
# Fact extraction (operates on already-redacted text)
# --------------------------------------------------------------------------- #
_RE_VERSION = re.compile(
    r"music\s*assistant[^\n]*?\bv?(\d+\.\d+\.\d+(?:[.\-][\w.]+)?)", re.IGNORECASE
)
_RE_VERSION_ALT = re.compile(
    r"\b(?:mass|server)\s+version[:\s]+v?(\d+\.\d+\.\d+(?:[.\-][\w.]+)?)",
    re.IGNORECASE,
)
_RE_SAFE_MODE = re.compile(
    r"safe[\s_]?mode\b[^\n]*\b(?:enabled|active|on|true)\b"
    r"|\b(?:starting|running|started)\b[^\n]*\bsafe[\s_]?mode",
    re.IGNORECASE,
)
# Provider setup failures. Captures the provider domain/name token.
_RE_PROVIDER_ERROR = re.compile(
    r"(?:error setting up|failed to set ?up|failed loading|error loading|"
    r"could not set ?up|unable to set ?up|error initializing)\s+"
    r"(?:the\s+)?(?:provider\s+)?['\"`]?([a-z0-9][a-z0-9_\- ]{1,40}?)['\"`]?"
    r"(?:\s+provider)?\b",
    re.IGNORECASE,
)

_RE_TRACEBACK_START = re.compile(r"^\s*Traceback \(most recent call last\):\s*$")
# The "ExceptionType: message" line that ends a traceback (not indented). Any
# dotted identifier is accepted — this is only evaluated *after* a traceback
# header, so custom exception names (e.g. "InvalidState") aren't dropped.
_RE_EXC_LINE = re.compile(r"^([A-Za-z_][\w.]*)(?:: (.*))?$")
_RE_TRACEBACK_CONT = (
    "During handling of the above exception",
    "The above exception was the direct cause",
)
_RE_LEADING_TS = re.compile(
    r"^\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[.,\d]*\s*"
)


def _normalise_msg(msg: str) -> str:
    """Collapse variable bits so similar exceptions share a fingerprint."""
    msg = re.sub(r"0x[0-9a-fA-F]+", "0x…", msg)
    msg = re.sub(r"\d+", "#", msg)
    return " ".join(msg.split())[:80]


def _extract_version(text: str) -> str | None:
    for pattern in (_RE_VERSION, _RE_VERSION_ALT):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _extract_safe_mode(text: str) -> bool:
    return bool(_RE_SAFE_MODE.search(text))


def _extract_provider_errors(text: str) -> list[ProviderEntry]:
    seen: dict[str, ProviderEntry] = {}
    for line in text.splitlines():
        match = _RE_PROVIDER_ERROR.search(line)
        if not match:
            continue
        raw = match.group(1).strip().lower().replace(" ", "_")
        if not raw or raw in {"the", "a", "provider"}:
            continue
        if raw not in seen:
            snippet = _RE_LEADING_TS.sub("", line).strip()[:200]
            seen[raw] = ProviderEntry(
                domain=raw,
                instance_id="",
                type="",
                enabled=True,
                loaded=False,
                available=False,
                last_error=snippet,
            )
    return list(seen.values())


def _extract_exceptions(text: str) -> list[ExceptionEntry]:
    lines = text.splitlines()
    counts: dict[str, int] = {}
    reps: dict[str, ExceptionEntry] = {}
    i = 0
    n = len(lines)
    while i < n:
        if not _RE_TRACEBACK_START.match(lines[i]):
            i += 1
            continue
        # Walk the (possibly chained) traceback block and keep the FINAL
        # exception as its representative, so a chained traceback counts once.
        j = i + 1
        exc_type: str | None = None
        exc_msg: str | None = None
        while j < n:
            stripped = lines[j].rstrip()
            # Blank lines and indented frame lines are part of the body.
            if not stripped or stripped[0] in (" ", "\t"):
                j += 1
                continue
            # A nested/chained traceback header: skip it and keep scanning.
            if _RE_TRACEBACK_START.match(stripped):
                j += 1
                continue
            # First non-indented content line → the exception line.
            match = _RE_EXC_LINE.match(stripped)
            if not match:
                break  # normal log resumed; traceback block ended
            exc_type = match.group(1)
            exc_msg = match.group(2)
            # Peek past blanks: only keep scanning if a chained exception
            # explicitly follows; otherwise this was the final exception.
            k = j + 1
            while k < n and not lines[k].strip():
                k += 1
            if k < n and any(c in lines[k] for c in _RE_TRACEBACK_CONT):
                j = k + 1
                continue
            j += 1
            break
        if exc_type:
            key = f"{exc_type}|{_normalise_msg(exc_msg or '')}"
            counts[key] = counts.get(key, 0) + 1
            if key not in reps:
                reps[key] = ExceptionEntry(
                    exc_type=exc_type,
                    fingerprint=key,
                    count=0,  # filled in below
                    message=(exc_msg or None),
                )
        i = max(j, i + 1)
    result: list[ExceptionEntry] = []
    for key, entry in reps.items():
        entry.count = counts[key]
        result.append(entry)
    result.sort(key=lambda e: e.count, reverse=True)
    return result


def scan_log(raw: bytes | str) -> Diagnostics:
    """Redact a raw log and reconstruct a ``Diagnostics(source="log")``."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    text = redact(raw)

    system = SystemInfo(
        version=_extract_version(text),
        safe_mode=_extract_safe_mode(text) or None,
    )
    return Diagnostics(
        schema_version=0,
        generated_at=None,
        system=system,
        providers=_extract_provider_errors(text),
        exceptions=_extract_exceptions(text),
        source="log",
    )
