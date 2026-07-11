"""RAG orchestration — ties docs / embeddings / retrieval / similar / judge.

One entry point, :func:`answer`, runs the whole docs-grounded-answer +
related-posts pipeline for a single post and returns a :class:`RagResult`
(or ``None``). It is wrapped so **any** failure degrades to ``None`` and leaves
the deterministic Tier-0/Tier-1 triage completely untouched.

Pipeline (≤ 1 embedding + ≤ 1 judge chat per post):

1. embed the post once,
2. hybrid-retrieve doc chunks (dense + BM25 + RRF),
3. ask the judge whether the docs answer it,
4. route to a confidence tier (HIGH / MEDIUM / LOW),
5. find related past posts (dense, or search fallback),
6. demote the tier if the answer matches a downvoted (suppressed) fingerprint.
"""

from __future__ import annotations

import hashlib

from . import ai, config, embeddings, similar
from .gh import GitHubClient, log
from .models import DocAnswer, DocChunk, DocHit, RagResult
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


def _best_dense(query_vec: list[float], doc_hits: list[DocHit]) -> float:
    if not query_vec or not doc_hits:
        return 0.0
    return max(cosine(query_vec, hit.chunk.embedding) for hit in doc_hits)


def answer(
    gh: GitHubClient,
    *,
    title: str,
    body: str,
    number: int,
    token: str,
    kind: str = "issue",
) -> RagResult | None:
    """Run the RAG pipeline for one post. ``None`` when disabled or on failure."""
    if not (config.AI_ENABLED and config.RAG_ENABLED):
        return None
    try:
        query_text = f"{title}\n\n{body}".strip()
        query_vec = embeddings.embed_text(query_text, token=token)
        if query_vec is None:
            # Embeddings unavailable (e.g. rate limited) → skip the whole layer.
            return None

        chunks = embeddings.load_docs_chunks(gh)
        doc_hits = retrieve_docs(query_vec, query_text, chunks)

        judge: DocAnswer | None = None
        if doc_hits:
            judge = ai.judge_answer(title, body, doc_hits, token=token)

        # Decide the confidence tier.
        if judge is not None:
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
        posts = embeddings.load_posts(gh)
        related = similar.find_related(
            gh,
            query_vec=query_vec,
            title=title,
            posts=posts,
            exclude_number=number,
            exclude_kind=kind,
        )

        result = RagResult(
            tier=tier,
            doc_answer=doc_answer,
            cited_chunks=cited_chunks,
            doc_hits=doc_hits,
            related_posts=related,
            suppressed=suppressed,
        )
        return result if result.has_output else None
    except Exception as exc:  # noqa: BLE001 — never let RAG break triage
        log(f"RAG layer skipped: {exc}")
        return None
