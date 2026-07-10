"""Tests for the Tier-1.5 doc-answer judge (ai.judge_answer)."""

import json

from ma_triage import ai, config
from ma_triage.models import DocChunk, DocHit


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


def _hit(cid="faq/x#h", text="some docs text"):
    return DocHit(
        chunk=DocChunk(
            id=cid, path="faq/x", url="https://x/faq/x/#h", title="X", heading="h",
            text=text, breadcrumbs=["X", "h"],
        ),
        score=0.5,
    )


def _payload(obj):
    return {"choices": [{"message": {"content": json.dumps(obj)}}]}


def _enable(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", True)


def test_judge_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", False)
    assert ai.judge_answer("t", "b", [_hit()], token="x") is None


def test_judge_no_hits_returns_none(monkeypatch):
    _enable(monkeypatch)
    assert ai.judge_answer("t", "b", [], token="x") is None


def test_judge_happy_path_filters_cited(monkeypatch):
    _enable(monkeypatch)
    obj = {
        "answers_question": True, "confidence": 0.9,
        "answer": "Try enabling multicast.",
        "cited_sections": ["faq/x#h", "totally-made-up"],
    }
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(_payload(obj)))
    result = ai.judge_answer("title", "body", [_hit("faq/x#h")], token="x")
    assert result is not None
    assert result.answers_question is True
    assert result.confidence == 0.9
    # Hallucinated id dropped; only the real section id survives.
    assert result.cited_sections == ["faq/x#h"]


def test_judge_http_error_returns_none(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        ai.requests, "post", lambda *a, **k: _Resp({"error": "no"}, status=429)
    )
    assert ai.judge_answer("t", "b", [_hit()], token="x") is None


def test_judge_malformed_returns_none(monkeypatch):
    _enable(monkeypatch)
    bad = {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(bad))
    assert ai.judge_answer("t", "b", [_hit()], token="x") is None


def test_judge_coerces_and_clamps(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(config, "MAX_DOC_ANSWER_CHARS", 10)
    obj = {
        "answers_question": True, "confidence": 5,  # out of range
        "answer": "x" * 100,  # too long
        "cited_sections": "not-a-list",
    }
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(_payload(obj)))
    result = ai.judge_answer("t", "b", [_hit()], token="x")
    assert result.confidence == 1.0
    assert len(result.answer) == 10
    assert result.cited_sections == []


def test_judge_messages_are_sanitized(monkeypatch):
    _enable(monkeypatch)
    hit = _hit(text="ping @maintainer see <script>")
    messages = ai.build_answer_messages("title @x", "body #1", [hit])
    blob = json.dumps(messages)
    assert "<script>" not in blob
    assert "@maintainer" not in blob  # mentions neutralised


def test_judge_shows_raw_cited_id_and_round_trips(monkeypatch):
    _enable(monkeypatch)
    cid = "faq/troubleshooting#networking"
    hit = _hit(cid)
    # The id must appear verbatim (no zero-width space injected after '#'), or the
    # model can't echo an id that survives the exact-match citation filter.
    content = ai.build_answer_messages("t", "b", [hit])[1]["content"]
    assert f"[{cid}]" in content
    assert "\u200b" not in content

    obj = {"answers_question": True, "confidence": 0.9, "answer": "a",
           "cited_sections": [cid]}
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(_payload(obj)))
    res = ai.judge_answer("t", "b", [hit], token="x")
    assert res.cited_sections == [cid]  # faithfully-echoed id is kept, not dropped
