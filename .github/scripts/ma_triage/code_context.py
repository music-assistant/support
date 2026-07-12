"""Bounded retrieval of relevant code from the official server repository.

Tier-1 should not classify a report from its wording alone. For one or two
reported providers, this module fetches a small fixed set of likely source files
at the reported release tag (falling back to ``dev``), extracts the line windows
that overlap the issue/diagnostics vocabulary, and returns a tightly capped
evidence block for the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import config
from .gh import GitHubClient, log
from .models import Diagnostics
from .providers import provider_manifest_domain

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.\-/]{3,}")
_ORIGIN_PATH = re.compile(r"(music_assistant/[A-Za-z0-9_./-]+\.py)")
_STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "assistant",
        "before",
        "click",
        "could",
        "error",
        "from",
        "have",
        "home",
        "music",
        "official",
        "player",
        "plugin",
        "provider",
        "running",
        "settings",
        "that",
        "their",
        "there",
        "these",
        "this",
        "when",
        "with",
        "version",
    }
)
_PROVIDER_FILES = (
    "manifest.json",
    "helpers.py",
    "__init__.py",
    "provider.py",
    "client.py",
    "ARCHITECTURE.md",
    "strings.json",
)
_PACKAGING_HINTS = (
    "binary",
    "dependency",
    "executable",
    "install",
    "missing",
    "not found",
    "path",
    "requirement",
)


@dataclass(frozen=True)
class _Snippet:
    path: str
    ref: str
    score: int
    text: str


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN.findall(text)
        if token.lower() not in _STOP_WORDS
    }


def _terms(title: str, body: str, diag: Diagnostics) -> set[str]:
    issue_terms = _tokens(f"{title}\n{body}")
    terms = set(issue_terms)
    for exc in diag.exceptions:
        exc_terms = _tokens(
            "\n".join(
                [
                    exc.exc_type,
                    exc.message or "",
                    exc.origin or "",
                    exc.traceback or "",
                ]
            )
        )
        # Diagnostics often contain unrelated background exceptions. Only let an
        # exception steer code retrieval when it overlaps the reported symptom.
        if issue_terms & exc_terms:
            terms.update(exc_terms)
    return set(sorted(terms, key=len, reverse=True)[:60])


def _origin_paths(
    diag: Diagnostics,
    terms: set[str],
    *,
    provider_prefixes: tuple[str, ...],
) -> set[str]:
    paths: set[str] = set()
    for exc in diag.exceptions:
        exc_text = "\n".join(
            [exc.exc_type, exc.message or "", exc.origin or "", exc.traceback or ""]
        )
        for value in (exc.origin, exc.traceback):
            if not value:
                continue
            for path in _ORIGIN_PATH.findall(value):
                if provider_prefixes:
                    if path.startswith(provider_prefixes):
                        paths.add(path)
                elif _tokens(exc_text) & terms:
                    paths.add(path)
    return paths


def _refs(version: str | None) -> list[str]:
    refs: list[str] = []
    candidate = (version or "").strip().lstrip("v")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:b[0-9]+|rc[0-9]+)?", candidate):
        refs.append(candidate)
    if config.SERVER_REF not in refs:
        refs.append(config.SERVER_REF)
    return refs


def _line_score(line: str, terms: set[str]) -> int:
    lowered = line.lower()
    return sum(min(len(term), 24) for term in terms if term in lowered)


def _excerpt(text: str, terms: set[str], max_chars: int = 1400) -> tuple[int, str]:
    lines = text.splitlines()
    ranked = sorted(
        (
            (_line_score(line, terms), index)
            for index, line in enumerate(lines)
        ),
        reverse=True,
    )
    ranked = [(score, index) for score, index in ranked if score > 0]
    if not ranked:
        return 0, ""

    selected: set[int] = set()
    blocks: list[str] = []
    selected_scores: list[int] = []
    used = 0
    for score, index in ranked[:8]:
        if index in selected:
            continue
        window = range(max(0, index - 3), min(len(lines), index + 4))
        rendered = "\n".join(f"L{line + 1}: {lines[line]}" for line in window)
        if used + len(rendered) + 2 > max_chars:
            continue
        blocks.append(rendered)
        selected_scores.append(score)
        selected.update(window)
        used += len(rendered) + 2
    if not blocks:
        return 0, ""
    excerpt = "\n\n".join(blocks)
    distinct_matches = sum(1 for term in terms if term in excerpt.lower())
    return max(selected_scores) + distinct_matches * 5, excerpt


def _fetch(
    gh: GitHubClient, path: str, refs: list[str]
) -> tuple[str, str] | None:
    for ref in refs:
        content = gh.get_raw_file(config.SERVER_REPO, path, ref=ref)
        if content is not None:
            return ref, content
    return None


def build(
    gh: GitHubClient,
    *,
    title: str,
    body: str,
    diagnostics: Diagnostics,
    provider_labels: set[str],
    version: str | None,
) -> str:
    """Return relevant official-code excerpts, or ``""`` on no useful match."""
    terms = _terms(title, body, diagnostics)
    if not terms:
        return ""

    domains = [
        provider_manifest_domain(label)
        for label in sorted(provider_labels, key=str.lower)[:2]
    ]
    prefixes = tuple(f"music_assistant/providers/{domain}/" for domain in domains)
    paths = _origin_paths(diagnostics, terms, provider_prefixes=prefixes)
    for domain in domains:
        root = f"music_assistant/providers/{domain}"
        paths.update(f"{root}/{name}" for name in _PROVIDER_FILES)

    combined = f"{title}\n{body}".lower()
    if any(hint in combined for hint in _PACKAGING_HINTS):
        paths.update({"Dockerfile", "Dockerfile.base"})

    refs = _refs(version)
    snippets: list[_Snippet] = []
    for path in sorted(paths):
        fetched = _fetch(gh, path, refs)
        if fetched is None:
            continue
        ref, content = fetched
        score, excerpt = _excerpt(content, terms)
        if score and excerpt:
            snippets.append(_Snippet(path=path, ref=ref, score=score, text=excerpt))

    snippets.sort(key=lambda snippet: (-snippet.score, snippet.path))
    rendered: list[str] = []
    for snippet in snippets[: config.MAX_CODE_CONTEXT_FILES]:
        block = f"SOURCE: {snippet.path} @ {snippet.ref}\n{snippet.text}"
        projected = sum(len(item) + 2 for item in rendered) + len(block)
        if projected > config.MAX_CODE_CONTEXT_CHARS:
            break
        rendered.append(block)
    if rendered:
        return "\n\n".join(rendered)
    log("No relevant server-code context found for Tier-1 assessment")
    return ""
