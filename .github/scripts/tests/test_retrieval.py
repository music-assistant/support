"""Tests for the pure-Python hybrid retrieval math."""

import math

from ma_triage import config, retrieval
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


def _page_chunk(cid, path, text, embedding):
    return DocChunk(
        id=cid, path=path, url=f"https://x/{cid}", title=path, heading=cid,
        text=text, breadcrumbs=[path], embedding=embedding,
    )


def _multi_section_corpus():
    # Three sections of one page all match the query; a second page matches
    # slightly less well. Without a cap the whole budget goes to page one.
    return [
        _page_chunk("net#a", "faq/net", "sonos multicast mdns discovery", [1.0, 0.0]),
        _page_chunk("net#b", "faq/net", "sonos multicast mdns settings", [0.99, 0.0]),
        _page_chunk("net#c", "faq/net", "sonos multicast mdns router", [0.98, 0.0]),
        _page_chunk("players#a", "settings/players", "sonos player options", [0.9, 0.1]),
    ]


def test_retrieve_docs_caps_chunks_per_page(monkeypatch):
    monkeypatch.setattr(config, "DOCS_MAX_PER_PAGE", 1)
    hits = retrieval.retrieve_docs(
        [1.0, 0.0], "sonos multicast mdns", _multi_section_corpus(), k=2
    )
    paths = [h.chunk.path for h in hits]
    assert len(paths) == len(set(paths)), "one page must not fill the budget"
    assert "settings/players" in paths


def test_retrieve_docs_per_page_cap_is_configurable(monkeypatch):
    monkeypatch.setattr(config, "DOCS_MAX_PER_PAGE", 2)
    hits = retrieval.retrieve_docs(
        [1.0, 0.0], "sonos multicast mdns", _multi_section_corpus(), k=3
    )
    paths = [h.chunk.path for h in hits]
    assert paths.count("faq/net") == 2
    assert paths.count("settings/players") == 1


def test_retrieve_docs_cap_never_returns_fewer_than_available(monkeypatch):
    # A cap must not starve the result when only one page is relevant at all.
    monkeypatch.setattr(config, "DOCS_MAX_PER_PAGE", 1)
    only_one_page = _multi_section_corpus()[:3]
    hits = retrieval.retrieve_docs([1.0, 0.0], "sonos multicast", only_one_page, k=6)
    assert len(hits) == 1


def test_retrieve_docs_empty():
    assert retrieval.retrieve_docs([1.0], "q", []) == []


# --- BM25F ------------------------------------------------------------------ #
def test_bm25f_keeps_a_short_title_from_being_swamped_by_a_long_body():
    """The claim that earns BM25F its place over a weighted concatenation.

    Both documents mention the term once. The first says it in a two-word
    title; the second buries it in a long body. Per-field length normalisation
    is what puts the first ahead.
    """
    titles = [retrieval.tokenize("sonos grouping"), retrieval.tokenize("unrelated")]
    bodies = [
        retrieval.tokenize("nothing to see here"),
        retrieval.tokenize("padding " * 200 + "grouping"),
    ]
    scores = retrieval.bm25f_scores(
        retrieval.tokenize("grouping"),
        {"title": titles, "body": bodies},
        {"title": 3.0, "body": 1.0},
    )
    assert scores[0] > scores[1]


def test_bm25f_returns_one_score_per_document_for_an_empty_query():
    """The contract holds even when the first field is the empty one."""
    scores = retrieval.bm25f_scores(
        [], {"title": [], "body": [["a"], ["b"], ["c"]]}, {"title": 1.0}
    )
    assert scores == [0.0, 0.0, 0.0]


def test_bm25f_ignores_a_term_no_document_carries():
    titles = [retrieval.tokenize("alpha"), retrieval.tokenize("beta")]
    scores = retrieval.bm25f_scores(
        retrieval.tokenize("gamma"), {"title": titles}, {"title": 1.0}
    )
    assert scores == [0.0, 0.0]
