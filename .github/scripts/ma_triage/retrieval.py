"""Local hybrid retrieval — dense cosine + BM25, fused with RRF.

No model cost: the incoming post is embedded **once** by the caller; everything
here is pure Python over the in-memory index (a few thousand vectors at most, so
plain lists are fast enough and keep the dependency footprint at zero).

* **Dense** cosine over the embedding vectors captures semantic similarity.
* **BM25** over tokenized breadcrumbs+body rescues exact tokens the embedder can
  blur — provider domains (``youtube_music``), error codes, CLI flags, etc.
* **Reciprocal Rank Fusion (RRF)** combines the two rankings without needing the
  scores to be on comparable scales.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from . import config
from .models import DocChunk, DocHit

_RE_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str | None) -> list[str]:
    """Lower-case tokeniser that also splits underscore-joined identifiers.

    ``youtube_music`` yields ``["youtube_music", "youtube", "music"]`` so both the
    exact domain and its parts contribute to BM25.
    """
    if not text:
        return []
    tokens: list[str] = []
    for raw in _RE_TOKEN.findall(text.lower()):
        tokens.append(raw)
        if "_" in raw:
            tokens.extend(part for part in raw.split("_") if part)
    return tokens


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (0.0 if either is empty)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def rank_by_cosine(query: list[float], vectors: list[list[float]]) -> list[int]:
    """Indices of ``vectors`` ordered by descending cosine to ``query``."""
    if not query:
        return []
    scored = [(i, cosine(query, vec)) for i, vec in enumerate(vectors)]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [i for i, score in scored if score > 0.0]


def bm25_scores(
    query_tokens: list[str], docs_tokens: list[list[str]]
) -> list[float]:
    """Okapi BM25 score of each document for the query."""
    n = len(docs_tokens)
    if n == 0 or not query_tokens:
        return [0.0] * n
    doc_len = [len(tokens) for tokens in docs_tokens]
    avgdl = sum(doc_len) / n if n else 0.0
    # Document frequency per term.
    df: Counter[str] = Counter()
    doc_counters: list[Counter[str]] = []
    for tokens in docs_tokens:
        counts = Counter(tokens)
        doc_counters.append(counts)
        for term in counts:
            df[term] += 1

    k1 = config.BM25_K1
    b = config.BM25_B
    query_terms = set(query_tokens)
    scores = [0.0] * n
    for term in query_terms:
        n_qi = df.get(term, 0)
        if n_qi == 0:
            continue
        idf = math.log(1 + (n - n_qi + 0.5) / (n_qi + 0.5))
        for i, counts in enumerate(doc_counters):
            freq = counts.get(term, 0)
            if not freq:
                continue
            denom = freq + k1 * (1 - b + b * (doc_len[i] / avgdl if avgdl else 0))
            scores[i] += idf * (freq * (k1 + 1)) / denom
    return scores


def rank_by_bm25(query_tokens: list[str], docs_tokens: list[list[str]]) -> list[int]:
    """Indices ordered by descending BM25 score (only positive scores kept)."""
    scores = bm25_scores(query_tokens, docs_tokens)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [i for i in order if scores[i] > 0.0]


def rrf(rank_lists: list[list[int]], *, k: int | None = None) -> dict[int, float]:
    """Reciprocal Rank Fusion: ``score(d) = Σ 1/(k + rank_in_list(d))``."""
    k = config.RRF_K if k is None else k
    fused: dict[int, float] = {}
    for ranking in rank_lists:
        for rank, idx in enumerate(ranking):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return fused


def retrieve_docs(
    query_vec: list[float] | None,
    query_text: str,
    chunks: list[DocChunk],
    *,
    k: int | None = None,
) -> list[DocHit]:
    """Hybrid retrieval → the top-``k`` :class:`DocHit` for a query."""
    if not chunks:
        return []
    top_k = config.DOCS_TOP_K if k is None else k

    dense_rank = rank_by_cosine(query_vec or [], [c.embedding for c in chunks])
    docs_tokens = [tokenize(f"{c.label} {c.text}") for c in chunks]
    lexical_rank = rank_by_bm25(tokenize(query_text), docs_tokens)

    fused = rrf([dense_rank, lexical_rank])
    if not fused:
        return []
    ordered = sorted(fused.items(), key=lambda pair: pair[1], reverse=True)
    return [DocHit(chunk=chunks[idx], score=score) for idx, score in ordered[:top_k]]
