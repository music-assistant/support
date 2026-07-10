"""Tests for the embeddings client + JSON index read/write/build."""

import json

import pytest

from conftest import FAKE_DIM, FakeGH, fake_embedding
from ma_triage import config, embeddings
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


def test_embed_texts_http_error_returns_none(monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post", lambda *a, **k: _Resp({"error": "no"}, status=429)
    )
    assert embeddings.embed_texts(["a"], token="x") is None


def test_embed_texts_count_mismatch_returns_none(monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post", lambda *a, **k: _Resp(_emb_payload([[1.0]]))
    )
    assert embeddings.embed_texts(["a", "b"], token="x") is None


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
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: None)
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
        {"id": "a", "embedding": [1.0] * FAKE_DIM}]}
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


def test_append_post_skip_on_embed_failure(monkeypatch):
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: None)
    gh = FakeGH()
    index, changed = embeddings.append_post(
        gh, {"kind": "issue", "number": 5, "title": "x", "body": "y"}, token="t"
    )
    assert index is None and changed is False
