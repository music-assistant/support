"""Locate and safely download issue attachments (untrusted input).

All issue content is untrusted. We therefore:
* only follow links to GitHub's own attachment hosts (allowlist),
* enforce a hard byte cap while streaming (never trust ``Content-Length``),
* never execute, import or otherwise interpret the downloaded bytes.

Two attachment shapes matter:
* **uploaded files** — ``…/user-attachments/files/<id>/<name>`` (and the legacy
  ``…/<owner>/<repo>/files/<id>/<name>``). These carry a filename, so we use the
  extension to tell a diagnostics report / log / media file apart.
* **inline media** — images, gifs and recordings become
  ``…/user-attachments/assets/<uuid>`` (no filename/extension). Used by the
  frontend form's "Screenshot or recording" field.
"""

from __future__ import annotations

import re

import requests

from . import config
from .gh import log

# Allowlisted "uploaded file" URL shapes (these have a filename we can inspect):
#   https://github.com/user-attachments/files/<id>/<name>
#   https://github.com/<owner>/<repo>/files/<id>/<name>   (legacy)
_RE_USER_FILE = re.compile(
    r"https://github\.com/user-attachments/files/\d+/[\w.\-]+"
)
_RE_LEGACY_FILE = re.compile(
    r"https://github\.com/[\w.\-]+/[\w.\-]+/files/\d+/[\w.\-]+"
)
# Allowlisted inline-media URL shapes (no filename — screenshots/recordings):
#   https://github.com/user-attachments/assets/<uuid>
#   https://user-images.githubusercontent.com/...   (legacy images)
_RE_ASSET = re.compile(
    r"https://github\.com/user-attachments/assets/[0-9a-fA-F\-]+"
)
_RE_USER_IMAGE = re.compile(
    r"https://user-images\.githubusercontent\.com/[\w./\-]+"
)

_FILE_PATTERNS = (_RE_USER_FILE, _RE_LEGACY_FILE)
_MEDIA_PATTERNS = (_RE_ASSET, _RE_USER_IMAGE)

# Our diagnostics report: music-assistant-diagnostics-*.json / .md. We also
# accept any *.json upload (the 2.9.6 endpoint can produce a plain
# "diagnostics.json"), and treat the human-readable .md variant as diagnostics.
_RE_DIAGNOSTICS_NAME = re.compile(
    r"music-assistant-diagnostics-[\w\-]*\.(json|md)$", re.IGNORECASE
)
_RE_JSON_NAME = re.compile(r"\.json$", re.IGNORECASE)
# Anything that looks like a log file.
_RE_LOG_NAME = re.compile(r"\.(log|txt)$", re.IGNORECASE)
# Media file extensions (screenshots/recordings sometimes arrive as files).
_RE_MEDIA_NAME = re.compile(
    r"\.(png|jpe?g|gif|webp|bmp|heic|mp4|mov|webm|mkv)$", re.IGNORECASE
)


def _dedup(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _match_all(body: str, patterns) -> list[str]:
    urls: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(body):
            urls.append(match.group(0))
    return urls


def extract_file_urls(body: str | None) -> list[str]:
    """Allowlisted *uploaded file* URLs (have a filename) in the body."""
    if not body:
        return []
    return _dedup(_match_all(body, _FILE_PATTERNS))


def extract_media_urls(body: str | None) -> list[str]:
    """Allowlisted *inline media* URLs (assets/user-images) in the body."""
    if not body:
        return []
    return _dedup(_match_all(body, _MEDIA_PATTERNS))


def extract_attachment_urls(body: str | None) -> list[str]:
    """All allowlisted attachment URLs (files + media)."""
    if not body:
        return []
    return _dedup(_match_all(body, (*_FILE_PATTERNS, *_MEDIA_PATTERNS)))


def _filename(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def find_diagnostics_url(body: str | None) -> str | None:
    """First uploaded file that is a diagnostics report (named or any .json/.md)."""
    files = extract_file_urls(body)
    # Prefer the canonical name, then fall back to any .json / diagnostics .md.
    for url in files:
        if _RE_DIAGNOSTICS_NAME.search(_filename(url)):
            return url
    for url in files:
        if _RE_JSON_NAME.search(_filename(url)):
            return url
    return None


def find_log_urls(body: str | None) -> list[str]:
    """Uploaded files that look like plain log files."""
    return [
        url for url in extract_file_urls(body) if _RE_LOG_NAME.search(_filename(url))
    ]


def find_media_urls(body: str | None) -> list[str]:
    """All media attachments: inline assets plus media-extension file uploads."""
    urls = list(extract_media_urls(body))
    urls += [
        url for url in extract_file_urls(body) if _RE_MEDIA_NAME.search(_filename(url))
    ]
    return _dedup(urls)


def has_media_attachment(body: str | None) -> bool:
    """True when the body contains at least one screenshot/recording/image."""
    return bool(find_media_urls(body))


def is_allowlisted(url: str) -> bool:
    return any(
        pattern.fullmatch(url)
        for pattern in (*_FILE_PATTERNS, *_MEDIA_PATTERNS)
    )


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


def download_log_windowed(
    url: str,
    *,
    head_bytes: int = config.MAX_DOWNLOAD_BYTES,
    tail_bytes: int = config.MAX_LOG_TAIL_BYTES,
) -> str | None:
    """Download a (possibly huge) log as a head window + best-effort tail window.

    Reads up to ``head_bytes`` from the start (captures the startup banner /
    version). If the file is larger, it additionally tries an HTTP ``Range``
    request for the last ``tail_bytes`` (captures the most recent errors). Ranges
    are best-effort — if unsupported we just return the head. Decoded as UTF-8
    with replacement; the caller must still redact before echoing anything.
    """
    if not is_allowlisted(url):
        log(f"Refusing to download non-allowlisted URL: {url}")
        return None

    head = bytearray()
    truncated = False
    try:
        with requests.get(
            url, stream=True, timeout=30, headers={"User-Agent": "ma-triage-bot"}
        ) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                head.extend(chunk)
                if len(head) >= head_bytes:
                    truncated = True
                    break
    except requests.RequestException as exc:
        log(f"Failed to download log {url}: {exc}")
        return None

    text = bytes(head[:head_bytes]).decode("utf-8", errors="replace")
    if not truncated:
        return text

    tail_text = _fetch_tail(url, tail_bytes)
    if tail_text:
        return f"{text}\n\n... [log truncated by triage bot] ...\n\n{tail_text}"
    return text


def _fetch_tail(url: str, tail_bytes: int) -> str | None:
    try:
        resp = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "ma-triage-bot",
                "Range": f"bytes=-{tail_bytes}",
            },
        )
    except requests.RequestException as exc:
        log(f"Tail fetch failed for {url}: {exc}")
        return None
    if resp.status_code != 206:  # server ignored the Range request
        return None
    return resp.content[:tail_bytes].decode("utf-8", errors="replace")
