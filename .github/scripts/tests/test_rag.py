"""Tests for the RAG orchestrator (rag.answer + tier/suppression logic)."""

import json

from conftest import FakeGH
from ma_triage import config, embeddings, rag
from ma_triage.models import DocAnswer, DocChunk


def _chunk(cid, text):
    return DocChunk(
        id=cid, path=cid.split("#")[0], url=f"https://x/{cid}", title="T",
        heading=cid, text=text, breadcrumbs=["T", cid], sha=text,
    )


def _gh_with_indexes(topic="sonos players discovered via mdns multicast"):
    """A FakeGH carrying a docs index and a posts index (built with fakes)."""
    gh = FakeGH()
    chunks = [_chunk("faq/net#mdns", topic), _chunk("faq/bill#pay", "unrelated billing")]
    idx, _ = embeddings.build_docs_index(gh, token="t", chunks=chunks)
    embeddings.save_index(gh, config.DOCS_INDEX_PATH, idx, message="d")
    pidx, _ = embeddings.build_posts_index(
        gh,
        [{"kind": "issue", "number": 50, "title": topic, "body": "",
          "url": "u50", "state": "open"}],
        token="t",
    )
    embeddings.save_index(gh, config.POSTS_INDEX_PATH, pidx, message="p")
    return gh


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def test_tier_for():
    assert rag.tier_for(0.9) == "high"
    assert rag.tier_for(0.5) == "medium"
    assert rag.tier_for(0.1) == "low"


def test_demote():
    assert rag.demote("high") == "medium"
    assert rag.demote("medium") == "low"
    assert rag.demote("low") == "low"


def test_fingerprint_stable_and_order_independent():
    assert rag.fingerprint(["a", "b"]) == rag.fingerprint(["b", "a"])
    assert rag.fingerprint(["a"]) != rag.fingerprint(["b"])


def test_is_suppressed():
    supp = [{"hash": rag.fingerprint(["a#x"]), "downvotes": 2}]
    assert rag.is_suppressed(rag.fingerprint(["a#x"]), supp) is True
    assert rag.is_suppressed(rag.fingerprint(["b#y"]), supp) is False


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def test_answer_disabled_returns_none(fake_gh):
    # AI_ENABLED defaults to False in the test environment.
    assert rag.answer(fake_gh, title="t", body="b", number=1, token="x") is None


def test_answer_returns_none_when_nothing_to_show(ai_on):
    # Enabled, but no docs index, no posts index, and no search hits -> None
    # (so apply_triage writes no stray RAG state block).
    gh = FakeGH()
    assert rag.answer(gh, title="random topic", body="text", number=1, token="t") is None


def test_answer_none_on_embed_failure(ai_on, monkeypatch):
    monkeypatch.setattr(embeddings, "embed_text", lambda text, *, token: None)
    gh = _gh_with_indexes()
    assert rag.answer(gh, title="sonos mdns", body="", number=1, token="t") is None


def test_answer_high_tier(ai_on, monkeypatch):
    gh = _gh_with_indexes()
    monkeypatch.setattr(
        rag.ai, "judge_answer",
        lambda t, b, hits, *, token: DocAnswer(
            True, 0.92, "Enable multicast on your network.", [hits[0].chunk.id]
        ),
    )
    res = rag.answer(gh, title="sonos not discovered", body="mdns multicast",
                     number=99, token="t")
    assert res is not None and res.tier == "high"
    assert res.doc_answer is not None
    assert res.cited_chunks and res.cited_chunks[0].id == "faq/net#mdns"
    assert [p.number for p in res.related_posts] == [50]
    assert res.has_docs_output is True


def test_answer_medium_tier_links_only(ai_on, monkeypatch):
    gh = _gh_with_indexes()
    monkeypatch.setattr(
        rag.ai, "judge_answer",
        lambda t, b, hits, *, token: DocAnswer(True, 0.55, "maybe", [hits[0].chunk.id]),
    )
    res = rag.answer(gh, title="sonos mdns", body="multicast", number=99, token="t")
    assert res.tier == "medium"
    assert res.doc_answer is None  # links only, no prose
    assert res.doc_hits  # links available for rendering


def test_answer_low_tier_still_shows_related(ai_on, monkeypatch):
    gh = _gh_with_indexes()
    monkeypatch.setattr(
        rag.ai, "judge_answer",
        lambda t, b, hits, *, token: DocAnswer(False, 0.1, "", []),
    )
    res = rag.answer(gh, title="sonos mdns", body="multicast", number=99, token="t")
    assert res.tier == "low"
    assert res.doc_answer is None
    assert res.cited_chunks == []
    # Duplicate/related detection is independent of the docs tier.
    assert res.related_posts
    assert res.has_output is True


def test_answer_judge_failure_falls_back_to_medium(ai_on, monkeypatch):
    gh = _gh_with_indexes()
    monkeypatch.setattr(rag.ai, "judge_answer", lambda *a, **k: None)
    res = rag.answer(gh, title="sonos mdns multicast", body="players discovered",
                     number=99, token="t")
    assert res.tier == "medium"
    assert res.doc_answer is None
    assert res.doc_hits


def test_answer_suppression_demotes(ai_on, monkeypatch):
    gh = _gh_with_indexes()
    # Pre-load a suppression fingerprint for the section the judge will cite.
    fp = rag.fingerprint(["faq/net#mdns"])
    gh._index_files[config.SUPPRESS_INDEX_PATH] = json.dumps(
        {"schema": 1, "fingerprints": [{"hash": fp, "downvotes": 3}]}
    )
    monkeypatch.setattr(
        rag.ai, "judge_answer",
        lambda t, b, hits, *, token: DocAnswer(True, 0.95, "answer", ["faq/net#mdns"]),
    )
    res = rag.answer(gh, title="sonos mdns", body="multicast", number=99, token="t")
    assert res.suppressed is True
    assert res.tier == "medium"  # demoted from high
    assert res.doc_answer is None


# --------------------------------------------------------------------------- #
# build_result wiring (AI on attaches RAG; AI off leaves it None)
# --------------------------------------------------------------------------- #
def test_build_result_wires_rag_when_enabled(ai_on, monkeypatch):
    from ma_triage import __main__ as main

    gh = _gh_with_indexes()
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: None)
    monkeypatch.setattr(main, "find_log_urls", lambda body: [])
    monkeypatch.setattr(
        rag.ai, "judge_answer",
        lambda t, b, hits, *, token: DocAnswer(True, 0.9, "a", [hits[0].chunk.id]),
    )
    body = (
        "### What happened?\n\nsonos mdns discovery\n\n"
        "### How to reproduce\n\nx\n\n"
        "### Music Assistant version\n\n2.9.5\n\n"
        "### How do you run Music Assistant?\n\nHome Assistant add-on"
    )
    res = main.build_result(
        gh, "sonos not discovered", body, token="t", labels=["triage"], number=99
    )
    assert res.rag is not None and res.rag.tier == "high"


def test_build_result_no_rag_when_disabled(fake_gh, monkeypatch):
    from ma_triage import __main__ as main

    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: None)
    monkeypatch.setattr(main, "find_log_urls", lambda body: [])
    res = main.build_result(fake_gh, "t", "b", token="t", labels=["triage"])
    assert res.rag is None
