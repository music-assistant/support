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
# One file's share of the evidence block, so the per-file and total budgets
# cannot contradict each other.
_EXCERPT_CHARS = config.MAX_CODE_CONTEXT_CHARS // config.MAX_CODE_CONTEXT_FILES
# The best-scoring window keeps its surroundings; later ones are tightened, so
# the budget reaches more of the file than it reaches around one line of it.
_EXCERPT_RADIUS = 3
_EXCERPT_RADIUS_TAIL = 1
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


def _excerpt(
    text: str, terms: set[str], max_chars: int = _EXCERPT_CHARS
) -> tuple[int, str]:
    """Score a file against ``terms``, and quote the lines that earned it.

    Returns ``(0, "")`` when no line matches. ``max_chars`` bounds the quoted
    text and is the only limit on how many windows it holds.
    """
    lines = text.splitlines()
    scored = [(_line_score(line, terms), index) for index, line in enumerate(lines)]
    # Highest score first; among equals the earliest line, which is where a
    # module's public surface sits.
    ranked = sorted(
        ((score, index) for score, index in scored if score > 0),
        key=lambda item: (-item[0], item[1]),
    )
    if not ranked:
        return 0, ""

    selected: set[int] = set()
    blocks: list[tuple[int, str]] = []
    selected_scores: list[int] = []
    used = 0
    for score, index in ranked:
        radius = _EXCERPT_RADIUS if not blocks else _EXCERPT_RADIUS_TAIL
        window = range(max(0, index - radius), min(len(lines), index + radius + 1))
        if selected.intersection(window):
            # Overlapping windows would quote the same line in two blocks, and
            # split one contiguous region into what reads as several places.
            continue
        rendered = "\n".join(f"L{line + 1}: {lines[line]}" for line in window)
        if used + len(rendered) + 2 > max_chars:
            continue
        blocks.append((index, rendered))
        selected_scores.append(score)
        selected.update(window)
        used += len(rendered) + 2
    if not blocks:
        return 0, ""
    excerpt = "\n\n".join(text for _, text in sorted(blocks))
    distinct_matches = sum(1 for term in terms if term in excerpt.lower())
    return max(selected_scores) + distinct_matches * 5, excerpt


def _quote_around(text: str, line: int, terms: set[str]) -> tuple[int, str]:
    """Quote ``line`` with its surroundings, scored as ``_excerpt`` scores.

    The score has to be on the same scale, because ``build`` ranks every
    candidate against every other one and keeps only the best few.
    """
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return 0, ""
    window = range(
        max(0, line - 1 - _EXCERPT_RADIUS),
        min(len(lines), line + _EXCERPT_RADIUS),
    )
    excerpt = "\n".join(f"L{index + 1}: {lines[index]}" for index in window)
    best = max(_line_score(lines[index], terms) for index in window)
    matched = sum(1 for term in terms if term in excerpt.lower())
    return best + matched * 5, excerpt


def _traced_excerpt(
    text: str, terms: set[str], location: dict[str, object]
) -> tuple[int, str]:
    """Quote the place the model pointed at, in the text that was fetched.

    The trace ran against a different tree, so its line number does not carry
    over; its enclosing definition does. The symbol is located here and the
    recorded offset applied to it. Where that cannot be done — the symbol has
    gone, or the file holds more than one of that name, or the offset runs past
    the end — the file is excerpted the ordinary way, which measures better
    than trusting the stale line.
    """
    symbol = str(location.get("symbol") or "")
    if not symbol:
        # Module level, so the line number is the only anchor there is — and it
        # was measured against a different tree, which is why it has to earn
        # its place against ordinary excerpting rather than replace it.
        score, excerpt = _quote_around(
            text, int(location.get("line") or 0), terms
        )
        return (score, excerpt) if score else _excerpt(text, terms)

    at = [
        text.count("\n", 0, match.start()) + 1
        for match in code_trace.DEFINITION.finditer(text)
        if match.group(2) == symbol
    ]
    if len(at) != 1:
        log(
            f"Traced symbol {symbol!r} is "
            + ("not unique here" if at else "no longer here")
            + "; excerpting instead"
        )
        return _excerpt(text, terms)

    score, excerpt = _quote_around(
        text, at[0] + int(location.get("offset") or 0), terms
    )
    # A window that matches nothing is worth less than the file's own best
    # lines, and `build` drops a zero-scored snippet outright.
    return (score, excerpt) if score else _excerpt(text, terms)


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
    reported = _origin_paths(diagnostics, issue_terms, provider_prefixes=prefixes)
    paths = set(reported)
    paths.update(_provider_paths(gh, domains, refs))

    combined = f"{title}\n{body}".lower()
    if any(hint in combined for hint in _PACKAGING_HINTS):
        paths.update({"Dockerfile", "Dockerfile.base"})

    traced = {str(item["path"]): item for item in code_trace.load()}
    paths.update(traced)

    snippets: list[_Snippet] = []
    for path in sorted(paths):
        fetched = _fetch(gh, path, refs)
        if fetched is None:
            continue
        ref, content = fetched
        location = traced.get(path)
        if location is not None:
            score, excerpt = _traced_excerpt(content, terms, location)
        else:
            score, excerpt = _excerpt(content, terms)
        if score and excerpt:
            snippets.append(
                _Snippet(
                    path=path,
                    ref=ref,
                    score=score,
                    text=excerpt,
                    # A path the traceback also named is hard evidence, and
                    # stays labelled as such even when the search found it too.
                    origin="reported" if path not in traced or path in reported
                    else "searched",
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
