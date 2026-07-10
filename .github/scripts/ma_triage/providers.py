"""Map provider domains to repo labels and resolve their (community) maintainers.

Maintainers come from each provider's ``manifest.json`` in the server repo. The
manifest uses a ``codeowners`` list of ``@handle`` entries (the older
``maintainers`` field is gone). Handles equal to the core team
(``@music-assistant``) are skipped — we only want to involve *community*
maintainers.
"""

from __future__ import annotations

import json
from functools import lru_cache

from . import config
from .gh import GitHubClient, log


def domain_to_label(domain: str) -> str:
    """Return the repo label for a provider domain (falls back to the domain)."""
    return config.PROVIDER_LABELS.get(domain, domain)


def filter_existing_labels(labels: set[str], existing: set[str]) -> set[str]:
    """Keep only labels that already exist in the repo (case-insensitive)."""
    lower_existing = {e.lower(): e for e in existing}
    result: set[str] = set()
    for label in labels:
        match = lower_existing.get(label.lower())
        if match:
            result.add(match)
    return result


@lru_cache(maxsize=256)
def _fetch_manifest(gh: GitHubClient, domain: str) -> str | None:
    return gh.get_raw_file(config.SERVER_REPO, config.MANIFEST_PATH.format(domain=domain))


def resolve_maintainers(gh: GitHubClient, domain: str) -> list[str]:
    """Return community maintainer handles (without ``@``) for a provider domain."""
    raw = _fetch_manifest(gh, domain)
    if not raw:
        return []
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        log(f"Manifest for {domain} is not valid JSON: {exc}")
        return []

    codeowners = manifest.get("codeowners")
    if not isinstance(codeowners, list):
        return []

    maintainers: list[str] = []
    for entry in codeowners:
        if not isinstance(entry, str):
            continue
        handle = entry.lstrip("@").strip()
        if not handle:
            continue
        # Skip the core team handle (and any team-style "org/team" entries).
        if handle.lower() == config.CORE_TEAM_HANDLE.lower():
            continue
        if "/" in handle:
            continue
        maintainers.append(handle)
    return maintainers
