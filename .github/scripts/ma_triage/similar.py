"""Related-post / duplicate detection.

Surfaces earlier issues and discussions that look similar to the incoming post,
so a reporter (and a maintainer) can spot an existing answer or a likely
duplicate. Two paths:

* **primary** — dense cosine over the ``posts.json`` embeddings index (semantic,
  free, catches rewordings),
* **lexical** — BM25F over the title and excerpt the same index stores, for when
  the query embedding is unavailable but the index text is still readable,
* **last resort** — GitHub's own issue search over the report's title keywords,
  when there is no readable index at all.

The incoming post's own number is always excluded, and results are de-duplicated
and thresholded so the comment only ever shows genuinely-relevant links.
"""

from __future__ import annotations

import re

from . import config, embeddings, template
from .gh import GitHubClient, log
from .models import RelatedPost
from .providers import detect_provider_labels_from_text
from .retrieval import bm25f_scores, cosine, decode_vec, tokenize

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
        score = cosine(query_vec, decode_vec(post.get("embedding")))
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
                excerpt=str(post.get("excerpt", "")),
            )
        )
    return results


def related_from_lexical(
    query_title: str,
    query_body: str,
    posts: list[dict],
    *,
    exclude_number: int,
    exclude_kind: str = "issue",
    provider_labels: set[str] | None = None,
    k: int | None = None,
) -> list[RelatedPost]:
    """BM25F related posts from the index text, with no embedding involved.

    Ranked on the same ``title`` + ``excerpt`` the index already stores, so this
    works against a file built while the embeddings provider was down. Recall@3
    over the mined duplicate pairs is 29% on 34 strong pairs and 28% on 110 weak
    ones, against 21% for the GitHub keyword search it displaces — but the
    reason to prefer it is reach, not ranking: the search path cannot be
    filtered by provider, so it is skipped entirely for the 56% of reports that
    name one.

    Results carry ``score=0.0``. BM25 is unbounded and corpus-relative, so its
    value is not comparable to the cosine every other consumer of that field
    expects; ``source`` is what callers branch on.

    There is deliberately no score threshold here. Measured against hard
    negatives — the other candidates returned for a query whose true duplicate
    is known — a raw BM25F score barely separates them (AUC 0.62), as an
    unbounded cross-query score should be expected not to. The best feature
    found was the top hit's lead over the runner-up (AUC 0.76), and gating on
    it at 1.10 lifts precision on that top hit from 21% to 42%. That is enough
    for a collapsed suggestion and not enough to assert a duplicate, which is
    why these never render expanded and why no constant is exposed.
    """
    top_k = config.RELATED_POSTS if k is None else k
    if not posts:
        return []
    required_providers = _provider_keys(provider_labels)

    candidates: list[dict] = []
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
        candidates.append(post)
    if not candidates:
        return []

    titles = [tokenize(post.get("title")) for post in candidates]
    bodies = [tokenize(post.get("excerpt")) for post in candidates]
    # Stripped to match the excerpts being ranked. While both carried the form's
    # consent block those terms cancelled out; against stripped excerpts they are
    # terms almost no document has, and idf rewards whichever still holds them.
    query = tokenize(f"{query_title}\n\n{template.strip_boilerplate(query_body)}")
    scores = bm25f_scores(
        query,
        {"title": titles, "body": bodies},
        # Title weighted over body. 2, 3 and 5 all measured identically over 110
        # mined pairs, so this is the middle of a flat region rather than a tuned
        # optimum — BM25F's per-field length normalisation is doing the work.
        {"title": 3.0, "body": 1.0},
    )
    ranked = sorted(
        (i for i, score in enumerate(scores) if score > 0.0),
        key=lambda i: -scores[i],
    )[:top_k]
    return [
        RelatedPost(
            kind=candidates[i].get("kind", "issue"),
            number=int(candidates[i].get("number", 0)),
            title=str(candidates[i].get("title", "")),
            url=str(candidates[i].get("url", "")),
            score=0.0,
            state=candidates[i].get("state"),
            excerpt=str(candidates[i].get("excerpt", "")),
            source="lexical",
        )
        for i in ranked
    ]


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
                excerpt=embeddings.post_excerpt(item.get("body")),
                source="search",
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
    body: str = "",
    text_posts: list[dict] | None = None,
    exclude_kind: str = "issue",
    provider_labels: set[str] | None = None,
) -> list[RelatedPost]:
    """Related posts, in descending order of what the available inputs support.

    Dense cosine when there is a query vector and vectors to compare it to,
    BM25F over the index text when there is not, and GitHub's issue search only
    when there is no readable index at all.

    The choice is made once for the whole request, not per record: a partially
    vectorless index (what a build during a provider outage produces) still
    takes the dense path, and its vectorless records are simply not candidates.
    Ranking the two together is fusion, which is a separate change.
    """
    if posts and query_vec:
        # The index is usable, so its verdict stands — including a verdict of
        # "nothing scored highly enough". Falling through to the keyword search
        # here would re-add unscored matches the score floor just rejected.
        return related_from_index(
            query_vec,
            posts,
            exclude_number=exclude_number,
            exclude_kind=exclude_kind,
            provider_labels=provider_labels,
        )
    if text_posts:
        # No vector, but the index text is readable — and unlike the search
        # below it can be filtered by provider, so this runs for every report
        # rather than only the ones naming no provider.
        return related_from_lexical(
            title,
            body,
            text_posts,
            exclude_number=exclude_number,
            exclude_kind=exclude_kind,
            provider_labels=provider_labels,
        )
    # Below here the only candidate source is GitHub's issue search, which
    # cannot be scoped to a provider. A report that names one would therefore
    # get back exactly the cross-provider matches `related_from_index` filters
    # out, so it gets nothing instead (the index path applies the same filter
    # and keeps its results).
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
        if len(mentioned) >= config.PINNED_MAX_PROVIDERS:
            # A general status/index notice listing many providers, not a notice
            # about the specific provider this report is about.
            continue
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
                source="pinned",
                excerpt=embeddings.post_excerpt(discussion.get("body")),
            )
        )
    return matches
