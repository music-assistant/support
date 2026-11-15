"""Map provider domains to repo labels and resolve their (community) maintainers.

Maintainers come from each provider's ``manifest.json`` in the server repo. The
manifest uses a ``codeowners`` list of ``@handle`` entries (the older
``maintainers`` field is gone). Handles equal to the core team
(``@music-assistant``) are skipped — we only want to involve *community*
maintainers.

Providers that live outside the server repository come from the community
catalog index. They are recognised by name and domain like any other provider,
but their maintainers are never pinged: the reporter is sent to their tracker.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from urllib.parse import urlparse

import requests

from . import config, template
from .gh import GitHubClient, error, log
from .models import CommunityProvider, ProviderDoc


# Every provider manifest on the server by domain; commands that detect providers load it first.
_MANIFESTS: dict[str, dict] = {}
# Every community catalog provider by domain; only triage loads it.
_COMMUNITY: dict[str, CommunityProvider] = {}

_RE_DOMAIN = re.compile(r"[a-z][a-z0-9_]*")
_RE_REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")


def domain_to_label(domain: str) -> str:
    """Return the repo label for a provider domain (falls back to the domain)."""
    return config.PROVIDER_LABELS.get(domain, domain)


def load_manifests(gh: GitHubClient) -> bool:
    """Read every provider manifest on the server once, for detection and lookups.

    Returns False when none could be read: detection then knows only the aliases
    in :data:`config.PROVIDER_TEXT_ALIASES`, so nothing that rewrites every stored
    post's providers should run on it.
    """
    if _MANIFESTS:
        return True
    files = gh.get_subdirectory_files(
        config.SERVER_REPO, config.PROVIDERS_DIR, "manifest.json", ref=config.SERVER_REF
    )
    for domain, raw in (files or {}).items():
        # `_demo_*` are templates whose codeowner is a placeholder handle.
        if domain.startswith("_"):
            continue
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError as exc:
            log(f"Manifest for {domain} is not valid JSON: {exc}")
            continue
        if isinstance(manifest, dict):
            _MANIFESTS[domain] = manifest
    if not _MANIFESTS:
        error(
            f"Could not read the provider manifests from {config.SERVER_REPO}@"
            f"{config.SERVER_REF}; only providers with a hand-written alias are recognised."
        )
        return False
    _alias_patterns.cache_clear()
    return True


def load_community_providers() -> bool:
    """
    Read the community catalog index once, for detection and referrals.

    Returns False when it could not be read: only providers in the server
    repository are then recognised, exactly as without the catalog.
    """
    if _COMMUNITY:
        return True
    try:
        resp = requests.get(
            config.COMMUNITY_INDEX_URL,
            timeout=config.COMMUNITY_INDEX_TIMEOUT,
            headers={"User-Agent": "ma-triage-bot"},
        )
        resp.raise_for_status()
        index = resp.json()
    except (requests.RequestException, ValueError) as exc:
        error(f"Could not read the community catalog index: {exc}")
        return False
    entries = index.get("providers") if isinstance(index, dict) else None
    for domain, entry in (entries if isinstance(entries, dict) else {}).items():
        provider = _parse_community_provider(domain, entry)
        if provider is not None:
            _COMMUNITY[domain] = provider
    _alias_patterns.cache_clear()
    return True


def community_provider(label: str) -> CommunityProvider | None:
    """Return the community catalog provider a detected label stands for, if any."""
    provider = _COMMUNITY.get(label)
    if provider is None or _shadowed_by_builtin(provider, _builtin_names()):
        return None
    return provider


@lru_cache(maxsize=1)
def _alias_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Compile aliases longest-first so specific plugin names win.

    Manifest names match only in their own casing, so the Audible provider is not
    every report that calls a sound "audible".
    """
    patterns: list[tuple[re.Pattern[str], str]] = []
    aliases = [
        (alias, label, re.IGNORECASE)
        for alias, label in config.PROVIDER_TEXT_ALIASES.items()
    ]
    aliases += [(name, label, 0) for name, label in _manifest_aliases().items()]
    aliases += [(name, label, 0) for name, label in _community_aliases().items()]
    aliases.sort(key=lambda item: len(item[0]), reverse=True)
    for alias, label, flags in aliases:
        # Word boundaries around the alias; tolerate spaces/underscores between
        # words ("youtube music" also matches "youtube_music").
        escaped = re.escape(alias).replace(r"\ ", r"[\s_]+")
        patterns.append((re.compile(rf"(?<![\w]){escaped}(?![\w])", flags), label))
    return patterns


def _manifest_aliases() -> dict[str, str]:
    """Map the manifest name of each provider with a community codeowner to its label."""
    aliases: dict[str, str] = {}
    for domain, manifest in _MANIFESTS.items():
        name = manifest.get("name")
        if not isinstance(name, str) or not _community_handles(manifest):
            continue
        name = _spoken_name(name)
        if name and name.lower() not in config.PROVIDER_TEXT_ALIASES:
            aliases[name] = domain_to_label(domain)
    return aliases


def _community_aliases() -> dict[str, str]:
    """Map the name and domain of each community catalog provider to its domain."""
    aliases: dict[str, str] = {}
    builtin = _builtin_names()
    for domain, provider in _COMMUNITY.items():
        if _shadowed_by_builtin(provider, builtin):
            continue
        name = _spoken_name(provider.name)
        if name:
            aliases[name] = domain
        # A domain that is just the name in lower case would match the plain
        # word, which the name's own-casing rule exists to avoid.
        if domain != name.lower():
            aliases[domain] = domain
    return aliases


def _spoken_name(name: str) -> str:
    """What reporters call a provider: "Emby", not "Emby Media Server Library"."""
    name = re.sub(r"\s*\(.*?\)", "", name).strip()
    for suffix in (" Media Server Library", " Provider", " Players"):
        name = name.removesuffix(suffix)
    return name


def detect_provider_labels_from_text(text: str | None) -> set[str]:
    """Suggest provider labels for provider names mentioned in free text.

    Uses the aliases in :data:`config.PROVIDER_TEXT_ALIASES` and the names read by
    :func:`load_manifests`, with word-boundary matching. Labels are filtered against
    the repo's real labels before they are applied, but a single detected provider
    also decides which codeowner is pinged.
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
    manifest = _MANIFESTS.get(provider_manifest_domain(provider))
    if manifest is not None:
        return manifest
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
    return _community_handles(_load_manifest(gh, domain))


def _community_handles(manifest: dict) -> list[str]:
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


def _builtin_names() -> set[str]:
    """Every name, alias, domain and label of a server repository provider, lower case."""
    names = {key.lower() for key in config.PROVIDER_TEXT_ALIASES}
    names |= {label.lower() for label in config.PROVIDER_TEXT_ALIASES.values()}
    names |= {key.lower() for key in config.PROVIDER_LABELS}
    names |= {label.lower() for label in config.PROVIDER_LABELS.values()}
    for domain, manifest in _MANIFESTS.items():
        names.add(domain.lower())
        name = manifest.get("name")
        if isinstance(name, str):
            names.add(_spoken_name(name).lower())
    return names


def _shadowed_by_builtin(provider: CommunityProvider, builtin: set[str]) -> bool:
    """True when a server repository provider already answers to its name or domain."""
    return (
        provider.domain.lower() in builtin
        or _spoken_name(provider.name).lower() in builtin
    )


def _parse_community_provider(domain: object, entry: object) -> CommunityProvider | None:
    if not isinstance(domain, str) or not _RE_DOMAIN.fullmatch(domain):
        return None
    if not isinstance(entry, dict):
        return None
    repository = entry.get("repository")
    if not isinstance(repository, str) or not _RE_REPOSITORY.fullmatch(repository):
        return None
    manifest = entry.get("manifest")
    if not isinstance(manifest, dict):
        manifest = {}
    name = manifest.get("name")
    reason = entry.get("reason")
    return CommunityProvider(
        domain=domain,
        name=name.strip() if isinstance(name, str) and name.strip() else domain,
        repository=repository,
        status=str(entry.get("status") or "listed"),
        reason=reason.strip() if isinstance(reason, str) and reason.strip() else None,
        reason_url=_safe_url(entry.get("reason_url")),
        support_url=_safe_url(manifest.get("support_url")),
        documentation=_safe_url(manifest.get("documentation")),
    )


def _safe_url(value: object) -> str | None:
    """Return the value when it is an https URL that is safe as a Markdown link target."""
    if not isinstance(value, str) or any(char in value for char in "\r\n\t \\[]()<>"):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return value
