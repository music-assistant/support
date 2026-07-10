"""Tests for related-post detection (dense index + search fallback)."""

from conftest import FAKE_DIM, fake_embedding
from ma_triage import config, similar


def _post(number, text, kind="issue", state="open"):
    return {
        "kind": kind, "number": number, "title": text, "url": f"https://x/{number}",
        "state": state, "embedding": fake_embedding(text),
    }


def test_related_from_index_ranks_and_thresholds():
    query = fake_embedding("sonos speaker grouping")
    posts = [
        _post(1, "sonos speaker grouping problem"),
        {"kind": "issue", "number": 2, "title": "unrelated", "url": "https://x/2",
         "state": "open", "embedding": [0.0] * FAKE_DIM},
    ]
    hits = similar.related_from_index(query, posts, exclude_number=99)
    assert [h.number for h in hits] == [1]  # #2 (zero vector) below the threshold


def test_related_from_index_excludes_self():
    query = fake_embedding("sonos speaker grouping")
    posts = [_post(1, "sonos speaker grouping problem")]
    assert similar.related_from_index(query, posts, exclude_number=1) == []


def test_related_from_index_respects_k(monkeypatch):
    monkeypatch.setattr(config, "RELATED_MIN_SCORE", 0.0)
    query = fake_embedding("alpha")
    posts = [_post(i, "alpha beta") for i in range(1, 6)]
    hits = similar.related_from_index(query, posts, exclude_number=99, k=2)
    assert len(hits) == 2


def test_related_from_search_filters_prs_and_self(fake_gh, monkeypatch):
    monkeypatch.setattr(
        fake_gh, "_search_items",
        [
            {"number": 10, "title": "matching issue", "html_url": "u10", "state": "open"},
            {"number": 11, "title": "a PR", "html_url": "u11", "pull_request": {}},
            {"number": 7, "title": "self", "html_url": "u7", "state": "open"},
        ],
        raising=False,
    )
    hits = similar.related_from_search(fake_gh, "streaming problem", exclude_number=7)
    numbers = [h.number for h in hits]
    assert 10 in numbers
    assert 11 not in numbers  # PR filtered
    assert 7 not in numbers  # self excluded


def test_find_related_falls_back_to_search_when_no_index_hits(fake_gh, monkeypatch):
    monkeypatch.setattr(
        fake_gh, "_search_items",
        [{"number": 42, "title": "fallback hit", "html_url": "u42", "state": "open"}],
        raising=False,
    )
    # Posts present but none similar -> index yields nothing -> search fallback.
    query = fake_embedding("sonos grouping")
    posts = [{"kind": "issue", "number": 1, "title": "x", "url": "u",
              "state": "open", "embedding": [0.0] * FAKE_DIM}]
    hits = similar.find_related(
        fake_gh, query_vec=query, title="sonos grouping", posts=posts,
        exclude_number=99,
    )
    assert [h.number for h in hits] == [42]


def test_find_related_uses_index_when_available(fake_gh):
    query = fake_embedding("sonos speaker grouping")
    posts = [{"kind": "issue", "number": 3, "title": "sonos speaker grouping",
              "url": "u3", "state": "open",
              "embedding": fake_embedding("sonos speaker grouping")}]
    hits = similar.find_related(
        fake_gh, query_vec=query, title="sonos speaker grouping", posts=posts,
        exclude_number=99,
    )
    assert [h.number for h in hits] == [3]
