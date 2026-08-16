"""Local hybrid retrieval — dense cosine + BM25/BM25F, fused with RRF.

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

import base64
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


class VectorFormatError(ValueError):
    """A stored embedding could not be decoded."""


def encode_vec(vec: list[float]) -> str:
    """
    Pack an embedding into base64 int8 for storage in the index.

    The index is committed to git and rewritten in full on every new post, so its
    on-disk size decides how many posts can be indexed at all. JSON float arrays
    cost ~9.7 KB per vector; this costs ~0.7 KB.

    Each component is scaled by the vector's own maximum magnitude before being
    rounded to a signed byte, and **that scale is not stored**. Decoded vectors
    are therefore only valid for direction-based comparison — :func:`cosine`
    normalises both operands, so the per-vector constant cancels. They are *not*
    valid for anything reading magnitude: dot-product scoring, Euclidean
    distance, or an absolute-distance threshold will all be wrong. Store the
    scale alongside if that is ever needed.

    Round-trip error measured on the live index is ~0.001 cosine, against a
    ~0.03 gap between the weakest confirmed duplicate and the strongest noise.
    """
    if not vec:
        return ""
    scale = max(abs(float(x)) for x in vec) or 1.0
    packed = bytes(
        max(-127, min(127, round(float(x) / scale * 127))) & 0xFF for x in vec
    )
    return base64.b64encode(packed).decode("ascii")


def decode_vec(raw: str | None) -> list[float]:
    """
    Unpack an embedding written by :func:`encode_vec`.

    Raises :class:`VectorFormatError` on anything unreadable rather than
    returning an empty vector. An empty vector scores 0.0 against every
    candidate, so swallowing the error would silently drop that post out of
    duplicate detection — the exact failure this encoding exists to fix, made
    invisible. Callers that must not fail hard already degrade at a higher
    level (see :func:`rag.answer`).

    Indexes written by an older schema are rejected wholesale by the vector
    load path (``embeddings._SCHEMA``), so this never has to interpret a legacy
    format. :func:`embeddings.load_posts_text` accepts older schemas for their
    text, and strips ``embedding`` from what it returns precisely so nothing it
    hands out can reach here.
    """
    if raw is None or raw == "":
        return []
    if not isinstance(raw, str):
        raise VectorFormatError(f"expected a base64 string, got {type(raw).__name__}")
    try:
        data = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise VectorFormatError("embedding is not valid base64") from exc
    return [float(byte - 256 if byte > 127 else byte) for byte in data]


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


def bm25f_scores(
    query_tokens: list[str],
    fields: dict[str, list[list[str]]],
    weights: dict[str, float],
) -> list[float]:
    """Fielded BM25 (BM25F) over documents split into named fields.

    Each field is length-normalised against its own average before the weights
    apply, so a short title keeps its pull against a long body instead of being
    swamped by it. That is what separates this from scoring a concatenation
    with the title repeated: field weight 2, 3 and 5 all measured the same,
    because the normalisation — not the multiplier — is doing the work.

    Saturation is applied once to the combined weighted frequency rather than
    per field, which is what makes that claim true; summing per-field BM25
    would not. :func:`bm25_scores` is the single-field, weight-1 case up to a
    constant factor — kept separate because merging them would rewrite the docs
    retrieval path for no gain here.

    Every field must supply one token list per document.
    """
    names = [name for name in fields if fields[name]]
    if not names or not query_tokens:
        n = next((len(docs) for docs in fields.values() if docs), 0)
        return [0.0] * n

    n = len(fields[names[0]])
    counts = {name: [Counter(doc) for doc in fields[name]] for name in names}
    norm: dict[str, list[float]] = {}
    for name in names:
        lengths = [sum(c.values()) for c in counts[name]]
        avg = sum(lengths) / n if n else 0.0
        norm[name] = [
            1 - config.BM25_B + config.BM25_B * (length / avg if avg else 0.0)
            for length in lengths
        ]

    df: Counter[str] = Counter()
    for i in range(n):
        seen: set[str] = set()
        for name in names:
            seen |= set(counts[name][i])
        df.update(seen)

    scores = [0.0] * n
    for term in set(query_tokens):
        n_qi = df.get(term, 0)
        if not n_qi:
            continue
        idf = math.log(1 + (n - n_qi + 0.5) / (n_qi + 0.5))
        for i in range(n):
            weighted = 0.0
            for name in names:
                freq = counts[name][i].get(term, 0)
                if freq:
                    weighted += weights.get(name, 1.0) * freq / norm[name][i]
            if weighted:
                scores[i] += idf * weighted / (config.BM25_K1 + weighted)
    return scores


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

    # Cap chunks per page. Several sections of one page tend to rank together,
    # which spends the budget re-describing a page the judge has already seen
    # instead of offering it another candidate. Measured over 78 questions whose
    # answering doc page is known, this lifts recall@6 from 64% to 71% and takes
    # the distinct pages shown from 4.3 to 6.
    per_page = max(1, config.DOCS_MAX_PER_PAGE)
    seen: dict[str, int] = {}
    hits: list[DocHit] = []
    for idx, score in ordered:
        path = chunks[idx].path.strip("/")
        if seen.get(path, 0) >= per_page:
            continue
        seen[path] = seen.get(path, 0) + 1
        hits.append(DocHit(chunk=chunks[idx], score=score))
        if len(hits) >= top_k:
            break
    return hits
