"""Tests for the embeddings client + JSON index read/write/build."""

import json

import pytest

from conftest import FAKE_DIM, FakeGH, fake_embedding
from ma_triage import config, embeddings
from ma_triage.retrieval import encode_vec
from ma_triage.models import DocChunk


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.content = b"x"

    def json(self):
        return self._payload

    @property
    def text(self):
        return json.dumps(self._payload)


def _emb_payload(vectors):
    return {"data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]}


def _chunk(cid, text):
    # sha == text so identical text reuses the cache, changed text invalidates it.
    return DocChunk(
        id=cid, path=cid.split("#")[0], url=f"https://x/{cid}", title="T",
        heading=cid, text=text, breadcrumbs=["T", cid], sha=text,
    )


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
def test_embed_texts_happy(monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post",
        lambda *a, **k: _Resp(_emb_payload([[1.0, 2.0], [3.0, 4.0]])),
    )
    assert embeddings.embed_texts(["a", "b"], token="x") == [[1.0, 2.0], [3.0, 4.0]]


def test_embed_texts_http_error_yields_none_per_input(monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post", lambda *a, **k: _Resp({"error": "no"}, status=429)
    )
    assert embeddings.embed_texts(["a"], token="x") == [None]


def test_embed_texts_count_mismatch_yields_none_per_input(monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post", lambda *a, **k: _Resp(_emb_payload([[1.0]]))
    )
    assert embeddings.embed_texts(["a", "b"], token="x") == [None, None]


def test_embed_texts_keeps_the_batches_that_succeeded(monkeypatch):
    """One failing batch must not discard the vectors already computed.

    A long backfill sends many batches. Collapsing them all into a single
    failure meant the last request timing out threw away everything before it,
    and since a vectorless record never satisfies the sha cache, the next run
    retried the whole backlog and could fail identically forever.
    """
    monkeypatch.setattr(config, "EMBED_BATCH", 1)
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            return _Resp({"error": "timeout"}, status=504)
        return _Resp(_emb_payload([[float(calls["n"])]]))

    monkeypatch.setattr(embeddings.requests, "post", flaky)
    assert embeddings.embed_texts(["a", "b", "c"], token="x") == [
        [1.0], None, [3.0]
    ]


def test_embed_text_single(monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post", lambda *a, **k: _Resp(_emb_payload([[9.0]]))
    )
    assert embeddings.embed_text("hello", token="x") == [9.0]


# --------------------------------------------------------------------------- #
# Docs index build + round-trip
# --------------------------------------------------------------------------- #
def test_build_docs_index_roundtrip(ai_on):
    gh = FakeGH()
    chunks = [_chunk("a#x", "sonos grouping"), _chunk("b#y", "spotify login")]
    index, changed = embeddings.build_docs_index(gh, token="t", chunks=chunks)
    assert changed is True and index is not None
    embeddings.save_index(gh, config.DOCS_INDEX_PATH, index, message="build")

    loaded = embeddings.load_docs_chunks(gh)
    assert {c.id for c in loaded} == {"a#x", "b#y"}
    assert all(len(c.embedding) == FAKE_DIM for c in loaded)


def test_build_docs_index_sha_cache(monkeypatch):
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    calls = []

    def spy(texts, *, token):
        calls.append(list(texts))
        return [fake_embedding(t) for t in texts]

    monkeypatch.setattr(embeddings, "embed_texts", spy)
    gh = FakeGH()

    index1, changed1 = embeddings.build_docs_index(
        gh, token="t", chunks=[_chunk("a#x", "alpha"), _chunk("b#y", "beta")]
    )
    assert changed1 is True and len(calls[-1]) == 2

    # Rebuild with identical content -> nothing re-embedded, unchanged.
    calls.clear()
    _, changed2 = embeddings.build_docs_index(
        gh, token="t", chunks=[_chunk("a#x", "alpha"), _chunk("b#y", "beta")],
        previous=index1,
    )
    assert changed2 is False
    assert calls == []  # cache hit for both chunks

    # Change only one chunk -> only that one is re-embedded.
    calls.clear()
    _, changed3 = embeddings.build_docs_index(
        gh, token="t",
        chunks=[_chunk("a#x", "alpha"), _chunk("b#y", "beta modified")],
        previous=index1,
    )
    assert changed3 is True
    assert len(calls[-1]) == 1


def test_build_docs_index_skip_on_limit(monkeypatch):
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: [None] * len(texts))
    gh = FakeGH()
    index, changed = embeddings.build_docs_index(
        gh, token="t", chunks=[_chunk("a#x", "alpha")]
    )
    assert index is None and changed is False


def test_save_index_dry_run_makes_no_commit():
    gh = FakeGH()
    gh.dry_run = True
    embeddings.save_index(gh, config.DOCS_INDEX_PATH, {"schema": 1}, message="m")
    assert config.DOCS_INDEX_PATH not in gh._index_files
    assert any(c[0] == "commit_files" for c in gh.calls)


def test_load_index_absent_and_malformed():
    assert embeddings.load_index(FakeGH(), "docs.json") is None
    gh = FakeGH(index_files={"docs.json": "{not json"})
    assert embeddings.load_index(gh, "docs.json") is None


def test_load_docs_chunks_model_mismatch_ignored(monkeypatch):
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    bad = {"model": "other/model", "dim": FAKE_DIM, "chunks": [
        {"id": "a", "embedding": encode_vec([1.0] * FAKE_DIM)}]}
    gh = FakeGH(index_files={config.DOCS_INDEX_PATH: json.dumps(bad)})
    assert embeddings.load_docs_chunks(gh) == []


# --------------------------------------------------------------------------- #
# Posts index build + incremental append
# --------------------------------------------------------------------------- #
def test_build_posts_index_and_append_dedupe(ai_on):
    gh = FakeGH()
    posts = [
        {"kind": "issue", "number": 1, "title": "sonos", "body": "b1",
         "url": "u1", "state": "open"},
        {"kind": "issue", "number": 2, "title": "spotify", "body": "b2",
         "url": "u2", "state": "closed"},
    ]
    index, changed = embeddings.build_posts_index(gh, posts, token="t")
    assert changed is True and len(index["posts"]) == 2
    embeddings.save_index(gh, config.POSTS_INDEX_PATH, index, message="posts")

    # Append an existing number -> upsert (still one record for #1).
    idx2, changed2 = embeddings.append_post(
        gh, {"kind": "issue", "number": 1, "title": "sonos v2", "body": "b1b",
             "url": "u1", "state": "open"}, token="t",
    )
    assert changed2 is True
    ones = [p for p in idx2["posts"] if p["number"] == 1]
    assert len(ones) == 1 and ones[0]["title"] == "sonos v2"

    # Append a brand-new number -> added.
    embeddings.save_index(gh, config.POSTS_INDEX_PATH, idx2, message="posts")
    idx3, _ = embeddings.append_post(
        gh, {"kind": "issue", "number": 3, "title": "tidal", "body": "b3",
             "url": "u3", "state": "open"}, token="t",
    )
    assert {p["number"] for p in idx3["posts"]} == {1, 2, 3}


def test_build_posts_index_truncates_long_body(monkeypatch):
    # A very long issue/discussion body must be capped before embedding so it
    # can't blow the model's token limit and fail the whole batch (see #posts).
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    captured = {}

    def spy(texts, *, token):
        captured["texts"] = texts
        return [fake_embedding(t) for t in texts]

    monkeypatch.setattr(embeddings, "embed_texts", spy)
    gh = FakeGH()
    long_body = "x" * (config.MAX_POST_EMBED_CHARS + 5000)
    posts = [{"kind": "issue", "number": 1, "title": "t", "body": long_body,
              "url": "u", "state": "open"}]
    index, _ = embeddings.build_posts_index(gh, posts, token="t")
    assert index is not None
    assert captured["texts"]
    assert all(len(t) <= config.MAX_POST_EMBED_CHARS for t in captured["texts"])


def test_append_post_writes_the_text_when_embedding_fails(monkeypatch):
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: [None] * len(texts))
    gh = FakeGH()
    index, embedded = embeddings.append_post(
        gh, {"kind": "issue", "number": 5, "title": "x", "body": "y"}, token="t"
    )
    assert embedded is False
    record = index["posts"][0]
    assert record["number"] == 5 and record["excerpt"] == "y"
    # Absent, never empty: `encode_vec([])` is also "", so an empty string would
    # merge "the encoder produced nothing" with "we never asked".
    assert "embedding" not in record
    assert index["vectors"] == 0


def test_append_post_keeps_an_existing_vector_when_embedding_fails(
    ai_on, monkeypatch
):
    """An edit during an outage must not cost a post the vector it already had."""
    gh = FakeGH()
    post = {"kind": "issue", "number": 5, "title": "x", "body": "y"}
    index, embedded = embeddings.append_post(gh, post, token="t")
    assert embedded is True
    embeddings.save_index(gh, config.POSTS_INDEX_PATH, index, message="seed")

    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: [None] * len(texts))
    index, embedded = embeddings.append_post(gh, post, token="t")
    assert embedded is True  # carried forward, not re-embedded
    assert index["posts"][0]["embedding"]


def test_append_post_drops_a_stale_vector_when_the_text_changed(ai_on, monkeypatch):
    """A vector may only travel with the text it was computed from."""
    gh = FakeGH()
    index, _ = embeddings.append_post(
        gh, {"kind": "issue", "number": 5, "title": "x", "body": "y"}, token="t"
    )
    embeddings.save_index(gh, config.POSTS_INDEX_PATH, index, message="seed")

    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: [None] * len(texts))
    index, embedded = embeddings.append_post(
        gh, {"kind": "issue", "number": 5, "title": "x", "body": "EDITED"}, token="t"
    )
    assert embedded is False
    assert "embedding" not in index["posts"][0]


def test_build_posts_index_refreshes_provider_metadata_without_reembedding(
    ai_on, monkeypatch
):
    gh = FakeGH()
    posts = [
        {
            "kind": "issue",
            "number": 1,
            "title": "Subsonic error",
            "body": "404",
            "providers": [],
        }
    ]
    previous, _ = embeddings.build_posts_index(gh, posts, token="t")
    calls = []
    monkeypatch.setattr(
        embeddings,
        "embed_texts",
        lambda texts, *, token: calls.append(texts) or [],
    )
    posts[0]["providers"] = ["subsonic"]
    updated, changed = embeddings.build_posts_index(
        gh, posts, token="t", previous=previous
    )
    assert changed is True
    assert calls == []
    assert updated["posts"][0]["providers"] == ["subsonic"]
    assert updated["posts"][0]["excerpt"] == "404"


# --- text-only loading (schema-tolerant, vector-free) ------------------------ #
def test_load_posts_text_accepts_a_legacy_schema_and_strips_vectors():
    """Schema 1 stored raw float lists, which `decode_vec` raises on by design.

    The text loader accepts those records for their text and removes the key,
    so nothing it returns can reach the decoder — a hard failure inside the
    path that exists to survive failure is the thing being avoided.
    """
    legacy = {"schema": 1, "model": "other/model", "dim": 999, "posts": [
        {"kind": "issue", "number": 1, "title": "sonos", "excerpt": "e",
         "embedding": [0.1, 0.2, 0.3]}]}
    gh = FakeGH(index_files={config.POSTS_INDEX_PATH: json.dumps(legacy)})
    posts = embeddings.load_posts_text(gh)
    assert [p["number"] for p in posts] == [1]
    assert "embedding" not in posts[0]
    # The vector path still rejects it, unchanged.
    assert embeddings.load_posts(gh) == []


def test_load_posts_text_keeps_records_with_no_vector(monkeypatch):
    """Posts indexed during an outage are exactly what this loader is for."""
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: [None] * len(texts))
    gh = FakeGH()
    index, _ = embeddings.append_post(
        gh, {"kind": "issue", "number": 5, "title": "x", "body": "y"}, token="t"
    )
    embeddings.save_index(gh, config.POSTS_INDEX_PATH, index, message="m")
    assert [p["number"] for p in embeddings.load_posts_text(gh)] == [5]
    assert embeddings.load_posts(gh) == []


def test_load_posts_text_rejects_an_unknown_schema():
    future = {"schema": 99, "posts": [{"kind": "issue", "number": 1, "title": "t"}]}
    gh = FakeGH(index_files={config.POSTS_INDEX_PATH: json.dumps(future)})
    assert embeddings.load_posts_text(gh) == []


def test_current_schema_has_a_known_text_layout():
    """Bumping `_SCHEMA` must be a decision about the text loader too.

    The lexical fallback reads the index through `_TEXT_COMPATIBLE_SCHEMAS`. If
    a bump forgets that list, the fallback goes silent at exactly the moment it
    is the only path left.
    """
    assert embeddings._SCHEMA in embeddings._TEXT_COMPATIBLE_SCHEMAS


# --- the index header describes the file, not the request -------------------- #
def test_index_records_the_width_actually_stored(ai_on, monkeypatch):
    """A provider free to ignore `dimensions` must not produce a lying header.

    `cosine` scores mismatched widths as 0.0, so a header that disagrees with
    its vectors shows up as duplicate detection quietly finding nothing.
    """
    monkeypatch.setattr(config, "EMBED_DIM", 0)  # request no particular width
    monkeypatch.setattr(
        embeddings, "embed_texts",
        lambda texts, *, token: [[0.5] * 7 for _ in texts],  # provider returns 7
    )
    gh = FakeGH()
    index, _ = embeddings.build_posts_index(
        gh, [{"kind": "issue", "number": 1, "title": "t", "body": "b",
              "url": "u", "state": "open"}], token="t",
    )
    assert index["dim"] == 7


def test_dim_matches_requires_the_requested_width_when_one_is_asked_for(monkeypatch):
    monkeypatch.setattr(config, "EMBED_DIM", 512)
    assert embeddings.dim_matches({"dim": 512})
    assert not embeddings.dim_matches({"dim": 1024})
    assert not embeddings.dim_matches({"dim": 0})


def test_dim_matches_accepts_any_real_width_when_none_is_requested(monkeypatch):
    monkeypatch.setattr(config, "EMBED_DIM", 0)
    assert embeddings.dim_matches({"dim": 1024})
    assert embeddings.dim_matches({"dim": 384})
    # 0 means no vectors were stored, so there is nothing to rank against.
    assert not embeddings.dim_matches({"dim": 0})
    assert not embeddings.dim_matches({})
