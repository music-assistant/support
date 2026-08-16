"""RAG orchestration — ties docs / embeddings / retrieval / similar / judge.

One entry point, :func:`answer`, runs the whole docs-grounded-answer +
related-posts pipeline for a single post and returns a :class:`RagResult`
(or ``None``). It is wrapped so **any** failure degrades to ``None`` and leaves
the deterministic Tier-0/Tier-1 triage completely untouched.

Pipeline (≤ 1 embedding + ≤ 1 judge chat per post):

1. embed the post once,
2. hybrid-retrieve doc chunks (dense + BM25 + RRF; skipped without a vector),
3. ask the judge whether the docs answer it,
4. route to a confidence tier (HIGH / MEDIUM / LOW),
5. find related past posts (dense, or search fallback),
6. demote the tier if the answer matches a downvoted (suppressed) fingerprint.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from . import ai, config, embeddings, similar
from .gh import GitHubClient, log
from .models import DocAnswer, DocChunk, DocHit, ProviderDoc, RagResult
from .retrieval import cosine, retrieve_docs


def tier_for(confidence: float) -> str:
    """Map a judge confidence to ``high`` / ``medium`` / ``low``."""
    if confidence >= config.ANSWER_HI:
        return "high"
    if confidence >= config.ANSWER_LO:
        return "medium"
    return "low"


def demote(tier: str) -> str:
    return {"high": "medium", "medium": "low"}.get(tier, "low")


def fingerprint(cited_sections: list[str]) -> str:
    """Stable fingerprint of an answer = hash of its sorted cited section ids."""
    joined = "|".join(sorted(cited_sections))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def is_suppressed(fp: str, suppress: list[dict]) -> bool:
    """True if ``fp`` has accumulated enough downvotes to be suppressed."""
    if not fp:
        return False
    for entry in suppress:
        if entry.get("hash") == fp:
            try:
                votes = int(entry.get("downvotes", 0))
            except (TypeError, ValueError):
                votes = 0
            return votes >= config.SUPPRESS_MIN_DOWNVOTES
    return False


def _resolve_cited(answer: DocAnswer, doc_hits: list[DocHit]) -> list[DocChunk]:
    by_id = {hit.chunk.id: hit.chunk for hit in doc_hits}
    chunks = [by_id[cid] for cid in answer.cited_sections if cid in by_id]
    if chunks:
        return chunks
    # The judge answered but cited nothing usable — fall back to the top hits.
    return [hit.chunk for hit in doc_hits[: config.DOCS_LINKS_SHOWN]]


def _best_dense(query_vec: list[float] | None, doc_hits: list[DocHit]) -> float:
    if not query_vec or not doc_hits:
        return 0.0
    return max(cosine(query_vec, hit.chunk.embedding) for hit in doc_hits)


def _promote_provider_docs(
    query_vec: list[float],
    chunks: list[DocChunk],
    hits: list[DocHit],
    provider_docs: list[ProviderDoc],
) -> list[DocHit]:
    """Ensure authoritative provider pages reach the judge/model evidence."""
    preferred_paths = {
        urlparse(doc.url).path.strip("/")
        for doc in provider_docs
        if urlparse(doc.url).path.strip("/")
    }
    if not preferred_paths:
        return hits
    preferred = [
        chunk
        for chunk in chunks
        if any(
            chunk.path.strip("/") == path
            or chunk.path.strip("/").startswith(path + "/")
            for path in preferred_paths
        )
    ]
    preferred.sort(
        key=lambda chunk: cosine(query_vec, chunk.embedding),
        reverse=True,
    )
    promoted = [
        DocHit(chunk=chunk, score=cosine(query_vec, chunk.embedding))
        for chunk in preferred[:2]
    ]
    seen = {hit.chunk.id for hit in promoted}
    promoted.extend(hit for hit in hits if hit.chunk.id not in seen)
    return promoted[: config.DOCS_TOP_K]


def answer(
    gh: GitHubClient,
    *,
    title: str,
    body: str,
    number: int,
    token: str,
    kind: str = "issue",
    provider_labels: set[str] | None = None,
    provider_docs: list[ProviderDoc] | None = None,
    duplicates_only: bool = False,
) -> RagResult | None:
    """Run the RAG pipeline for one post. ``None`` when disabled or on failure.

    With ``duplicates_only`` the docs judge is skipped entirely (saving the chat
    call) and only likely-duplicate related posts are kept — used for categories
    where a docs answer is never appropriate but a duplicate still is.
    """
    if not (config.AI_ENABLED and config.RAG_ENABLED):
        return None
    pinned = similar.find_pinned(gh, provider_labels)
    try:
        query_text = f"{title}\n\n{body}".strip()
        query_vec = embeddings.embed_text(query_text, token=token)

        # A docs answer needs the query vector. Without one `retrieve_docs`
        # ranks on its BM25 leg alone, and the judge would then be paid to
        # grade candidates nothing dense ever scored. Related posts carry no
        # such requirement, so they are still resolved below: pinned notices
        # and duplicate detection both stay useful while the embeddings
        # provider is unavailable.
        doc_hits: list[DocHit] = []
        if query_vec is not None:
            chunks = embeddings.load_docs_chunks(gh)
            doc_hits = retrieve_docs(query_vec, query_text, chunks)
            doc_hits = _promote_provider_docs(
                query_vec,
                chunks,
                doc_hits,
                provider_docs or [],
            )

        judge: DocAnswer | None = None
        if doc_hits and not duplicates_only:
            judge = ai.judge_answer(title, body, doc_hits, token=token)

        # Decide the confidence tier.
        if duplicates_only:
            # No docs section at all — not even the links-only fallback below,
            # which would otherwise fire purely on retrieval strength.
            doc_hits = []
            tier = "low"
        elif judge is not None:
            tier = tier_for(judge.confidence) if judge.answers_question else "low"
        elif doc_hits and _best_dense(query_vec, doc_hits) >= config.DOCS_MIN_DENSE:
            # Judge call failed but retrieval is strong → links-only MEDIUM.
            tier = "medium"
        else:
            tier = "low"

        # Suppression: demote if this answer shape was previously downvoted.
        suppressed = False
        cited_ids = judge.cited_sections if judge else [h.chunk.id for h in doc_hits[:1]]
        fp = fingerprint(cited_ids)
        if tier in ("high", "medium") and is_suppressed(
            fp, embeddings.load_suppress(gh)
        ):
            tier = demote(tier)
            suppressed = True

        # Resolve what the comment will render for the docs section.
        doc_answer: DocAnswer | None = None
        cited_chunks: list[DocChunk] = []
        if tier == "high" and judge is not None and judge.answers_question:
            doc_answer = judge
            cited_chunks = _resolve_cited(judge, doc_hits)

        # Related posts are independent of the docs tier (dupes may post even
        # when the docs answer is LOW).
        posts = embeddings.load_posts(gh) if query_vec else []
        related = similar.find_related(
            gh,
            query_vec=query_vec,
            title=title,
            body=body,
            posts=posts,
            text_posts=embeddings.load_posts_text(gh) if not posts else None,
            exclude_number=number,
            exclude_kind=kind,
            provider_labels=provider_labels,
        )
        if duplicates_only:
            # Only likely duplicates justify commenting on these categories, so
            # apply the same bar the comment uses to render a match expanded.
            # Only a dense cosine can clear this bar. A lexical or search hit
            # carries 0.0 by construction, so the `source` check is what makes
            # the intent explicit rather than leaving it to a sentinel: nothing
            # but semantic similarity may assert a duplicate on its own.
            related = [
                post
                for post in related
                if post.source == "dense"
                and post.score >= config.RELATED_EXPAND_SCORE
            ]

        result = RagResult(
            tier=tier,
            doc_answer=doc_answer,
            cited_chunks=cited_chunks,
            doc_hits=doc_hits,
            pinned_posts=pinned,
            related_posts=related,
            suppressed=suppressed,
            judge_confidence=judge.confidence if judge else None,
            judge_answered=judge.answers_question if judge else None,
            duplicates_only=duplicates_only,
        )
        return result if result.has_output else None
    except Exception as exc:  # noqa: BLE001 — never let RAG break triage
        log(f"RAG layer skipped: {exc}")
        result = RagResult(pinned_posts=pinned)
        return result if result.has_output else None
