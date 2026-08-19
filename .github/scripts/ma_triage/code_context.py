"""Bounded retrieval of relevant code from the official server repository.

Tier-1 should not classify a report from its wording alone. Candidate files come
from three places — the directories of the providers the reporter named, the
paths in a traceback that matches the reported symptom, and, when tracing is
enabled, a search of the source by the model itself. Whatever chose them, this
module fetches their contents at the reported release tag (falling back to
``dev``), keeps the line windows that overlap the issue vocabulary, and returns
a tightly capped evidence block that says how each file was chosen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import code_trace, config
from .gh import GitHubClient, log
from .models import Diagnostics, ExceptionEntry
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
_MAX_PROVIDER_FILES = 10
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
    # How the path was chosen. A file the traceback named is hard evidence; one
    # a search picked out is a candidate, and the model has to be able to tell
    # them apart before it weighs either against the reporter's account.
    origin: str


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN.findall(text)
        if token.lower() not in _STOP_WORDS
    }


def _exc_text(exc: ExceptionEntry) -> str:
    return "\n".join(
        [exc.exc_type, exc.message or "", exc.origin or "", exc.traceback or ""]
    )


def _terms(diag: Diagnostics, issue_terms: set[str]) -> set[str]:
    """Scoring vocabulary: the report, plus exceptions that corroborate it."""
    terms = set(issue_terms)
    for exc in diag.exceptions:
        exc_terms = _tokens(_exc_text(exc))
        # Diagnostics often contain unrelated background exceptions. Only let an
        # exception steer code retrieval when it overlaps the reported symptom.
        if issue_terms & exc_terms:
            terms.update(exc_terms)
    return set(sorted(terms, key=len, reverse=True)[:60])


def _origin_paths(
    diag: Diagnostics,
    issue_terms: set[str],
    *,
    provider_prefixes: tuple[str, ...],
) -> set[str]:
    """Source paths named by the exceptions, scoped to the reported problem.

    A path inside a reported provider's directory is evidence on its own. With
    no provider to scope by, the exception earns its place only by overlapping
    the reporter's own words.
    """
    paths: set[str] = set()
    for exc in diag.exceptions:
        describes_report = bool(issue_terms & _tokens(_exc_text(exc)))
        for value in (exc.origin, exc.traceback):
            if not value:
                continue
            for path in _ORIGIN_PATH.findall(value):
                if provider_prefixes:
                    if path.startswith(provider_prefixes):
                        paths.add(path)
                elif describes_report:
                    paths.add(path)
    return paths


def _provider_paths(
    gh: GitHubClient, domains: list[str], refs: list[str]
) -> set[str]:
    """The files in each reported provider's directory, shallowest first.

    Providers carry parsers, models, auth helpers and subpackages under names of
    their own choosing, so the directory is the only authority on what is there.
    Depth orders the candidates because a provider's own modules sit beside its
    ``__init__.py`` while subpackages hold the details.
    """
    if not domains:
        return set()
    roots = tuple(f"music_assistant/providers/{domain}/" for domain in domains)
    for ref in refs:
        tree = gh.get_tree(config.SERVER_REPO, ref)
        if not tree:
            continue
        paths: set[str] = set()
        for root in roots:
            in_root = sorted(
                (
                    str(entry.get("path", ""))
                    for entry in tree
                    if entry.get("type") == "blob"
                    and str(entry.get("path", "")).startswith(root)
                ),
                key=lambda path: (path.count("/"), path),
            )
            paths.update(in_root[:_MAX_PROVIDER_FILES])
        return paths
    return set()


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
    issue_terms = _tokens(f"{title}\n{body}")
    terms = _terms(diagnostics, issue_terms)
    if not terms:
        return ""

    domains = [
        provider_manifest_domain(label)
        for label in sorted(provider_labels, key=str.lower)[:2]
    ]
    prefixes = tuple(f"music_assistant/providers/{domain}/" for domain in domains)
    refs = _refs(version)
    paths = _origin_paths(diagnostics, issue_terms, provider_prefixes=prefixes)
    paths.update(_provider_paths(gh, domains, refs))

    combined = f"{title}\n{body}".lower()
    if any(hint in combined for hint in _PACKAGING_HINTS):
        paths.update({"Dockerfile", "Dockerfile.base"})

    traced = code_trace.load()
    paths.update(traced)

    snippets: list[_Snippet] = []
    for path in sorted(paths):
        fetched = _fetch(gh, path, refs)
        if fetched is None:
            continue
        ref, content = fetched
        score, excerpt = _excerpt(content, terms)
        if score and excerpt:
            snippets.append(
                _Snippet(
                    path=path,
                    ref=ref,
                    score=score,
                    text=excerpt,
                    origin="searched" if path in traced else "reported",
                )
            )

    snippets.sort(key=lambda snippet: (-snippet.score, snippet.path))
    rendered: list[str] = []
    for snippet in snippets[: config.MAX_CODE_CONTEXT_FILES]:
        block = (
            f"SOURCE: {snippet.path} @ {snippet.ref} ({snippet.origin})\n"
            f"{snippet.text}"
        )
        projected = sum(len(item) + 2 for item in rendered) + len(block)
        if projected > config.MAX_CODE_CONTEXT_CHARS:
            break
        rendered.append(block)
    if rendered:
        return "\n\n".join(rendered)
    log("No relevant server-code context found for Tier-1 assessment")
    return ""
