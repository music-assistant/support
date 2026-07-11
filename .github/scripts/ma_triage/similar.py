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
from .retrieval import cosine

_RE_WORD = re.compile(r"[A-Za-z0-9]+")


def related_from_index(
    query_vec: list[float] | None,
    posts: list[dict],
    *,
    exclude_number: int,
    exclude_kind: str = "issue",
    k: int | None = None,
    min_score: float | None = None,
) -> list[RelatedPost]:
    """Dense-cosine related posts from the loaded posts index (pure)."""
    if not query_vec or not posts:
        return []
    top_k = config.RELATED_POSTS if k is None else k
    threshold = config.RELATED_MIN_SCORE if min_score is None else min_score

    scored: list[tuple[float, dict]] = []
    seen: set[tuple[str, int]] = set()
    for post in posts:
        number = int(post.get("number", 0))
        kind = post.get("kind", "issue")
        if kind == exclude_kind and number == exclude_number:
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
) -> list[RelatedPost]:
    """Related posts from the index when available, else the search fallback."""
    if posts and query_vec:
        hits = related_from_index(
            query_vec, posts, exclude_number=exclude_number, exclude_kind=exclude_kind
        )
        if hits:
            return hits
    return related_from_search(
        gh, title, exclude_number=exclude_number, exclude_kind=exclude_kind
    )
