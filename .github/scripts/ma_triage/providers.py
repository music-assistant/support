"""Map provider domains to repo labels and resolve their (community) maintainers.

Maintainers come from each provider's ``manifest.json`` in the server repo. The
manifest uses a ``codeowners`` list of ``@handle`` entries (the older
``maintainers`` field is gone). Handles equal to the core team
(``@music-assistant``) are skipped — we only want to involve *community*
maintainers.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from urllib.parse import urlparse

from . import config, template
from .gh import GitHubClient, log
from .models import ProviderDoc


def domain_to_label(domain: str) -> str:
    """Return the repo label for a provider domain (falls back to the domain)."""
    return config.PROVIDER_LABELS.get(domain, domain)


@lru_cache(maxsize=1)
def _alias_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Compile aliases longest-first so specific plugin names win."""
    patterns: list[tuple[re.Pattern[str], str]] = []
    aliases = sorted(
        config.PROVIDER_TEXT_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for alias, label in aliases:
        # Word boundaries around the alias; tolerate spaces/underscores between
        # words ("youtube music" also matches "youtube_music").
        escaped = re.escape(alias).replace(r"\ ", r"[\s_]+")
        patterns.append((re.compile(rf"(?<![\w]){escaped}(?![\w])", re.IGNORECASE), label))
    return patterns


def detect_provider_labels_from_text(text: str | None) -> set[str]:
    """Suggest provider labels for provider names mentioned in free text.

    Uses the alias map in :data:`config.PROVIDER_TEXT_ALIASES` with word-boundary
    matching. Returned labels are still filtered against the repo's real labels by
    the caller, so a false positive can only surface a label that already exists.
    """
    if not text:
        return set()
    found: set[str] = set()
    claimed_spans: list[tuple[int, int]] = []
    for pattern, label in _alias_patterns():
        for match in pattern.finditer(text):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in claimed_spans):
                continue
            found.add(label)
            claimed_spans.append(span)
    return found


def detect_reported_provider_labels(
    title: str | None, body: str | None
) -> set[str]:
    """Identify the provider(s) the reporter says are affected.

    A provider named in the title is the strongest signal and wins over incidental
    mentions in the body (for example, "filesystem is wrong; Plex is fine"). If
    the title has no provider, scan the issue-form problem/reproduction fields;
    for older issues and Discussions without form sections, fall back to the full
    body.
    """
    title_labels = detect_provider_labels_from_text(title)
    if title_labels:
        return title_labels
    form_text = template.provider_scan_text(body)
    return detect_provider_labels_from_text(form_text or body)


def filter_existing_labels(labels: set[str], existing: set[str]) -> set[str]:
    """Keep only labels that already exist in the repo (case-insensitive)."""
    lower_existing = {e.lower(): e for e in existing}
    result: set[str] = set()
    for label in labels:
        match = lower_existing.get(label.lower())
        if match:
            result.add(match)
    return result


def provider_manifest_domain(provider: str) -> str:
    """Map a diagnostics domain or repo label to the current server domain."""
    lowered = provider.strip().lower()
    override = config.PROVIDER_MANIFEST_DOMAINS.get(lowered)
    if override:
        return override
    if lowered in config.PROVIDER_LABELS:
        return lowered
    for domain, label in config.PROVIDER_LABELS.items():
        if label.lower() == lowered:
            return domain
    return lowered


@lru_cache(maxsize=256)
def _fetch_manifest(gh: GitHubClient, domain: str) -> str | None:
    return gh.get_raw_file(
        config.SERVER_REPO,
        config.MANIFEST_PATH.format(domain=provider_manifest_domain(domain)),
        ref=config.SERVER_REF,
    )


def _load_manifest(gh: GitHubClient, provider: str) -> dict:
    raw = _fetch_manifest(gh, provider)
    if not raw:
        return {}
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        log(f"Manifest for {provider} is not valid JSON: {exc}")
        return {}
    return manifest if isinstance(manifest, dict) else {}


def resolve_maintainers(gh: GitHubClient, domain: str) -> list[str]:
    """Return community maintainer handles (without ``@``) for a provider domain."""
    manifest = _load_manifest(gh, domain)
    codeowners = manifest.get("codeowners")
    if not isinstance(codeowners, list):
        return []

    maintainers: list[str] = []
    for entry in codeowners:
        if not isinstance(entry, str):
            continue
        handle = entry.lstrip("@").strip()
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", handle):
            continue
        # Skip the core team handle (and any team-style "org/team" entries).
        if handle.lower() == config.CORE_TEAM_HANDLE.lower():
            continue
        if "/" in handle:
            continue
        maintainers.append(handle)
    return maintainers


def resolve_provider_doc(gh: GitHubClient, provider: str) -> ProviderDoc | None:
    """Return a safe documentation link from the provider manifest."""
    manifest = _load_manifest(gh, provider)
    raw_url = manifest.get("documentation")
    if not isinstance(raw_url, str):
        return None
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "music-assistant.io" or host.endswith(".music-assistant.io")
    ):
        return None
    if any(char in raw_url for char in "\r\n\\[]()<>"):
        return None
    name = manifest.get("name")
    return ProviderDoc(
        label=domain_to_label(provider_manifest_domain(provider)),
        name=str(name).strip() if isinstance(name, str) and name.strip() else provider,
        url=raw_url,
    )
