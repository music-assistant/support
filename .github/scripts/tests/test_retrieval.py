"""Tests for the pure-Python hybrid retrieval math."""

import math

from ma_triage import retrieval
from ma_triage.models import DocChunk


def _chunk(cid, text, embedding):
    return DocChunk(
        id=cid, path=cid, url=f"https://x/{cid}", title=cid, heading=cid,
        text=text, breadcrumbs=[cid], embedding=embedding,
    )


def test_tokenize_splits_underscores():
    toks = retrieval.tokenize("YouTube_Music playback error_code 42")
    assert "youtube_music" in toks
    assert "youtube" in toks and "music" in toks
    assert "42" in toks


def test_cosine_basic():
    assert retrieval.cosine([1, 0], [1, 0]) == 1.0
    assert retrieval.cosine([1, 0], [0, 1]) == 0.0
    assert retrieval.cosine([], [1]) == 0.0
    assert abs(retrieval.cosine([1, 1], [1, 0]) - 1 / math.sqrt(2)) < 1e-9


def test_rank_by_cosine_orders_desc():
    query = [1.0, 0.0]
    vecs = [[0.0, 1.0], [1.0, 0.0], [0.7, 0.7]]
    assert retrieval.rank_by_cosine(query, vecs)[0] == 1  # perfect match first
    # Orthogonal vector (score 0) is dropped.
    assert 0 not in retrieval.rank_by_cosine(query, vecs)


def test_bm25_rewards_rare_terms():
    docs_tokens = [
        ["sonos", "playback", "stops"],
        ["spotify", "login", "fails"],
        ["general", "playback", "info"],
    ]
    scores = retrieval.bm25_scores(["sonos"], docs_tokens)
    assert scores[0] > 0
    assert scores[1] == 0.0
    # "sonos" (rare) should make doc 0 the top hit.
    assert retrieval.rank_by_bm25(["sonos"], docs_tokens)[0] == 0


def test_rrf_fuses_rankings():
    # Item 2 is ranked highly by both lists -> should win the fusion.
    fused = retrieval.rrf([[0, 2, 1], [2, 1, 0]])
    best = max(fused.items(), key=lambda kv: kv[1])[0]
    assert best == 2


def test_retrieve_docs_hybrid(monkeypatch):
    chunks = [
        _chunk("a", "sonos speaker grouping", [1.0, 0.0, 0.0]),
        _chunk("b", "spotify premium login", [0.0, 1.0, 0.0]),
        _chunk("c", "general playback notes", [0.0, 0.0, 1.0]),
    ]
    # Query vector closest to chunk "a"; query text also mentions "sonos".
    hits = retrieval.retrieve_docs([0.9, 0.1, 0.0], "sonos grouping issue", chunks, k=2)
    assert hits[0].chunk.id == "a"
    assert len(hits) == 2


def test_retrieve_docs_empty():
    assert retrieval.retrieve_docs([1.0], "q", []) == []
