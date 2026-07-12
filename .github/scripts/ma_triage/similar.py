"""Related-post / duplicate detection.

Surfaces earlier issues and discussions that look similar to the incoming post,
so a reporter (and a maintainer) can spot an existing answer or a likely
duplicate. Two paths:

* **primary** — dense cosine over the ``posts.json`` embeddings index (semantic,
  free, catches rewordings),
* **fallback** — when the index is absent/empty, degrade gracefully to GitHub's
  own issue search over the report's title keywords.

The incoming post's own number is always excluded, and results are de-duplicated
and thresholded so the comment only ever shows genuinely-relevant links.
"""

from __future__ import annotations

import re

from . import config
from .gh import GitHubClient, log
from .models import RelatedPost
from .providers import detect_provider_labels_from_text
from .retrieval import cosine

_RE_WORD = re.compile(r"[A-Za-z0-9]+")


def _provider_keys(labels: set[str] | list[str] | None) -> set[str]:
    return {str(label).strip().lower() for label in (labels or []) if str(label).strip()}


def _post_provider_keys(post: dict) -> set[str]:
    stored = _provider_keys(post.get("providers"))
    if stored:
        return stored
    # Backwards compatibility until the next posts-index rebuild adds metadata.
    return _provider_keys(
        detect_provider_labels_from_text(str(post.get("title", "")))
    )


def related_from_index(
    query_vec: list[float] | None,
    posts: list[dict],
    *,
    exclude_number: int,
    exclude_kind: str = "issue",
    provider_labels: set[str] | None = None,
    k: int | None = None,
    min_score: float | None = None,
) -> list[RelatedPost]:
    """Dense-cosine related posts from the loaded posts index (pure)."""
    if not query_vec or not posts:
        return []
    top_k = config.RELATED_POSTS if k is None else k
    threshold = config.RELATED_MIN_SCORE if min_score is None else min_score
    required_providers = _provider_keys(provider_labels)

    scored: list[tuple[float, dict]] = []
    seen: set[tuple[str, int]] = set()
    for post in posts:
        number = int(post.get("number", 0))
        kind = post.get("kind", "issue")
        if kind == exclude_kind and number == exclude_number:
            continue
        if required_providers and not (required_providers & _post_provider_keys(post)):
            continue
        key = (kind, number)
        if key in seen:
            continue
        seen.add(key)
        score = cosine(query_vec, [float(x) for x in post.get("embedding", [])])
        if score >= threshold:
            scored.append((score, post))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results: list[RelatedPost] = []
    for score, post in scored[:top_k]:
        results.append(
            RelatedPost(
                kind=post.get("kind", "issue"),
                number=int(post.get("number", 0)),
                title=str(post.get("title", "")),
                url=str(post.get("url", "")),
                score=round(score, 4),
                state=post.get("state"),
            )
        )
    return results


def _title_query(title: str) -> str:
    """Reduce a (untrusted) title to plain keywords for a search query."""
    words = _RE_WORD.findall(title or "")
    # Drop very short/noise words and cap the number of terms.
    keywords = [w for w in words if len(w) > 2][:8]
    return " ".join(keywords)


def related_from_search(
    gh: GitHubClient, title: str, *, exclude_number: int, exclude_kind: str = "issue",
    k: int | None = None
) -> list[RelatedPost]:
    """Fallback: GitHub issue search over the title keywords."""
    top_k = config.RELATED_POSTS if k is None else k
    keywords = _title_query(title)
    if not keywords:
        return []
    query = f"repo:{gh.repo} is:issue {keywords}"
    try:
        data = gh.search_issues(query, per_page=top_k + 5)
    except Exception as exc:  # noqa: BLE001
        log(f"Related-post search fallback failed: {exc}")
        return []
    results: list[RelatedPost] = []
    for item in data.get("items", []) or []:
        if "pull_request" in item:
            continue
        number = int(item.get("number", 0))
        # The search only returns issues, so only skip the self-number when the
        # incoming post is itself an issue (a discussion sharing that number is
        # a different post and should still be surfaceable).
        if exclude_kind == "issue" and number == exclude_number:
            continue
        results.append(
            RelatedPost(
                kind="issue",
                number=number,
                title=str(item.get("title", "")),
                url=str(item.get("html_url", "")),
                score=0.0,
                state=item.get("state"),
            )
        )
        if len(results) >= top_k:
            break
    return results


def find_related(
    gh: GitHubClient,
    *,
    query_vec: list[float] | None,
    title: str,
    posts: list[dict],
    exclude_number: int,
    exclude_kind: str = "issue",
    provider_labels: set[str] | None = None,
) -> list[RelatedPost]:
    """Related posts from the index when available, else the search fallback."""
    if posts and query_vec:
        hits = related_from_index(
            query_vec,
            posts,
            exclude_number=exclude_number,
            exclude_kind=exclude_kind,
            provider_labels=provider_labels,
        )
        if hits:
            return hits
    # If the report names a provider, an unscoped text-search fallback can only
    # reintroduce the noisy cross-provider matches this filter is meant to stop.
    if provider_labels:
        return []
    return related_from_search(
        gh, title, exclude_number=exclude_number, exclude_kind=exclude_kind
    )


def find_pinned(
    gh: GitHubClient, provider_labels: set[str] | None
) -> list[RelatedPost]:
    """Pinned support notices that mention an affected provider exactly."""
    required = _provider_keys(provider_labels)
    if not required:
        return []
    matches: list[RelatedPost] = []
    try:
        discussions = gh.list_pinned_discussions()
    except Exception as exc:  # noqa: BLE001
        log(f"Pinned discussion matching failed: {exc}")
        return []
    for discussion in discussions:
        category = ((discussion.get("category") or {}).get("name") or "").lower()
        if category in config.PINNED_EXCLUDE_CATEGORIES:
            continue
        text = f"{discussion.get('title', '')}\n{discussion.get('body', '')}"
        mentioned = _provider_keys(detect_provider_labels_from_text(text))
        if not (required & mentioned):
            continue
        matches.append(
            RelatedPost(
                kind="discussion",
                number=int(discussion.get("number", 0)),
                title=str(discussion.get("title", "")),
                url=str(discussion.get("url", "")),
                score=1.0,
                state="closed" if discussion.get("closed") else "open",
            )
        )
    return matches
