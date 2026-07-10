"""Locate and safely download issue attachments (untrusted input).

All issue content is untrusted. We therefore:
* only follow links to GitHub's own attachment hosts (allowlist),
* enforce a hard byte cap while streaming (never trust ``Content-Length``),
* never execute, import or otherwise interpret the downloaded bytes.
"""

from __future__ import annotations

import re

import requests

from . import config
from .gh import log

# Allowlisted attachment URL shapes:
#   https://github.com/user-attachments/files/<id>/<name>
#   https://github.com/<owner>/<repo>/files/<id>/<name>   (legacy)
_RE_USER_ATTACHMENT = re.compile(
    r"https://github\.com/user-attachments/files/\d+/[\w.\-]+"
)
_RE_LEGACY_ATTACHMENT = re.compile(
    r"https://github\.com/[\w.\-]+/[\w.\-]+/files/\d+/[\w.\-]+"
)

# Our diagnostics file: music-assistant-diagnostics-YYYY-MM-DD-HHMMSS.json (or .md)
_RE_DIAGNOSTICS_NAME = re.compile(
    r"music-assistant-diagnostics-[\w\-]*\.(json|md)$", re.IGNORECASE
)
# Anything that looks like a log file.
_RE_LOG_NAME = re.compile(r"\.(log|txt)$", re.IGNORECASE)


def extract_attachment_urls(body: str | None) -> list[str]:
    """Return all allowlisted attachment URLs found in the issue body."""
    if not body:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for match in _RE_USER_ATTACHMENT.finditer(body):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    for match in _RE_LEGACY_ATTACHMENT.finditer(body):
        url = match.group(0)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _filename(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def find_diagnostics_url(body: str | None) -> str | None:
    """Return the first attachment that matches our diagnostics filename."""
    for url in extract_attachment_urls(body):
        if _RE_DIAGNOSTICS_NAME.search(_filename(url)):
            return url
    return None


def find_log_urls(body: str | None) -> list[str]:
    """Return attachment URLs that look like plain log files."""
    return [
        url
        for url in extract_attachment_urls(body)
        if _RE_LOG_NAME.search(_filename(url))
    ]


def is_allowlisted(url: str) -> bool:
    return bool(_RE_USER_ATTACHMENT.fullmatch(url) or _RE_LEGACY_ATTACHMENT.fullmatch(url))


def download_capped(url: str, *, max_bytes: int = config.MAX_DOWNLOAD_BYTES) -> bytes | None:
    """Stream-download an allowlisted URL, aborting past ``max_bytes``.

    Returns the raw bytes, or ``None`` on any problem (blocked host, too large,
    network error). The caller must treat the bytes as untrusted data.
    """
    if not is_allowlisted(url):
        log(f"Refusing to download non-allowlisted URL: {url}")
        return None

    try:
        with requests.get(
            url,
            stream=True,
            timeout=30,
            headers={"User-Agent": "ma-triage-bot"},
        ) as resp:
            resp.raise_for_status()
            # Reject early if the server advertises an oversized body.
            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                log(f"Attachment too large (declared {declared} bytes): {url}")
                return None
            chunks = bytearray()
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                chunks.extend(chunk)
                if len(chunks) > max_bytes:
                    log(f"Attachment exceeded {max_bytes} bytes while streaming: {url}")
                    return None
            return bytes(chunks)
    except requests.RequestException as exc:
        log(f"Failed to download {url}: {exc}")
        return None
