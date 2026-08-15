"""Tests for the stored-embedding codec and the per-kind index trim."""

from __future__ import annotations

import math

import pytest

from ma_triage import config, embeddings
from ma_triage.retrieval import VectorFormatError, cosine, decode_vec, encode_vec


def _vec(seed: int, dim: int = 64) -> list[float]:
    """A deterministic pseudo-embedding with both signs and a non-unit scale."""
    return [math.sin(seed * (i + 1) * 0.7) * 0.31 for i in range(dim)]


# --- codec ------------------------------------------------------------------ #
def test_round_trip_preserves_direction():
    original = _vec(1)
    restored = decode_vec(encode_vec(original))
    assert len(restored) == len(original)
    # The scale is intentionally discarded, so compare direction, not values.
    assert cosine(original, restored) == pytest.approx(1.0, abs=1e-3)


def test_pairwise_similarity_survives_quantisation():
    a, b = _vec(2), _vec(3)
    before = cosine(a, b)
    after = cosine(decode_vec(encode_vec(a)), decode_vec(encode_vec(b)))
    assert after == pytest.approx(before, abs=5e-3)


def test_scale_is_not_stored_so_magnitude_is_not_preserved():
    """Documents the contract: decoded vectors are for cosine only."""
    small = [0.001, 0.002, -0.001]
    large = [1000.0, 2000.0, -1000.0]
    # Same direction, wildly different magnitude -> identical encoding.
    assert encode_vec(small) == encode_vec(large)


def test_empty_vector_round_trips_to_empty():
    assert encode_vec([]) == ""
    assert decode_vec("") == []
    assert decode_vec(None) == []


@pytest.mark.parametrize("bad", ["not base64!!", "@@@@", 12345, ["a", "b"], {"x": 1}])
def test_unreadable_embedding_raises_rather_than_scoring_zero(bad):
    """A silent [] would score 0.0 against everything and hide the post."""
    with pytest.raises(VectorFormatError):
        decode_vec(bad)


def test_encoding_is_substantially_smaller_than_json():
    import json

    vec = _vec(4, dim=512)
    assert len(encode_vec(vec)) * 4 < len(json.dumps(vec))


# --- per-kind trim ---------------------------------------------------------- #
def test_trim_keeps_each_kind_up_to_its_own_cap(monkeypatch):
    monkeypatch.setattr(config, "INDEX_MAX_ISSUES", 2)
    monkeypatch.setattr(config, "INDEX_MAX_DISCUSSIONS", 1)
    records = [
        {"kind": "issue", "number": 5},
        {"kind": "discussion", "number": 4},
        {"kind": "issue", "number": 3},
        {"kind": "discussion", "number": 2},
        {"kind": "issue", "number": 1},
    ]
    kept = embeddings.trim_by_kind(records)
    assert [(r["kind"], r["number"]) for r in kept] == [
        ("issue", 5),
        ("discussion", 4),
        ("issue", 3),
    ]


def test_discussions_cannot_evict_issues(monkeypatch):
    """The regression that motivated per-kind caps: a burst of discussions
    previously pushed older issues out of a single shared budget."""
    monkeypatch.setattr(config, "INDEX_MAX_ISSUES", 3)
    monkeypatch.setattr(config, "INDEX_MAX_DISCUSSIONS", 3)
    records = [{"kind": "discussion", "number": n} for n in range(100, 90, -1)]
    records += [{"kind": "issue", "number": n} for n in range(3, 0, -1)]
    kept = embeddings.trim_by_kind(records)
    assert sum(1 for r in kept if r["kind"] == "issue") == 3
    assert sum(1 for r in kept if r["kind"] == "discussion") == 3


def test_unknown_kind_falls_back_to_the_issue_cap(monkeypatch):
    monkeypatch.setattr(config, "INDEX_MAX_ISSUES", 1)
    kept = embeddings.trim_by_kind([{"kind": "wat", "number": 2}, {"kind": "wat", "number": 1}])
    assert len(kept) == 1
