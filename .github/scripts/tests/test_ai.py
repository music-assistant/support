import json

from ma_triage import ai, config
from ma_triage.diagnostics import parse_diagnostics
from ma_triage.models import DocChunk, DocHit, ProviderDoc, RagResult, RelatedPost


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


def _ok_payload():
    content = json.dumps({
        "summary": "s", "likely_root_cause": "rc", "category": "bug",
        "confidence": 0.8, "possibly_fixed_in_version": None,
        "suggested_labels": ["sonos"], "user_message": "hi",
        "evidence": ["helpers.py says the binary is bundled"],
        "maintainer_next_step": "Inspect the release image.",
    })
    return {"choices": [{"message": {"content": content}}]}


def test_assess_disabled_returns_none(sample_raw, monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", False)
    diag = parse_diagnostics(sample_raw)
    assert ai.assess(diag, "t", "b", token="x") is None


def test_assess_happy_path(sample_raw, monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(_ok_payload()))
    diag = parse_diagnostics(sample_raw)
    result = ai.assess(diag, "title", "body", token="x")
    assert result is not None
    assert result.category == "bug"
    assert result.confidence == 0.8
    assert result.suggested_labels == ["sonos"]
    assert result.evidence == ["helpers.py says the binary is bundled"]
    assert result.maintainer_next_step == "Inspect the release image."


def test_assess_filters_suggested_labels_to_candidates(sample_raw, monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(_ok_payload()))
    diag = parse_diagnostics(sample_raw)
    result = ai.assess(
        diag, "title", "body", token="x", candidate_labels=["snapcast"]
    )
    assert result.suggested_labels == []


def test_strict_schema_requires_every_property():
    schema = ai._OUTPUT_SCHEMA["schema"]
    assert set(schema["required"]) == set(schema["properties"])


def test_build_messages_includes_docs_posts_and_code(sample_raw):
    diag = parse_diagnostics(sample_raw)
    chunk = DocChunk(
        id="plugins/spotify-connect#setup",
        path="plugins/spotify-connect",
        url="https://music-assistant.io/plugins/spotify-connect/",
        title="Spotify Connect",
        heading="Setup",
        text="The official add-on bundles go-librespot.",
    )
    rag = RagResult(
        doc_hits=[DocHit(chunk, 0.8)],
        pinned_posts=[
            RelatedPost(
                "discussion",
                709,
                "MA Status",
                "u709",
                excerpt="Spotify status notice",
            )
        ],
        related_posts=[
            RelatedPost(
                "issue",
                5731,
                "Spotify Connect race",
                "u5731",
                score=0.75,
                excerpt="Multiple Spotify Connect instances race.",
            )
        ],
    )
    messages = ai.build_messages(
        diag,
        "Spotify Connect go-librespot error",
        "binary not found",
        ["Spotify Connect"],
        rag_result=rag,
        provider_docs=[
            ProviderDoc(
                "Spotify Connect",
                "Spotify Connect",
                "https://music-assistant.io/plugins/spotify-connect/",
            )
        ],
        code_context=(
            "SOURCE: Dockerfile.base @ 2.9.7\n"
            "RUN install go-librespot /usr/local/bin/go-librespot"
        ),
    )
    content = messages[1]["content"]
    assert "OFFICIAL DOC SECTIONS" in content
    assert "PINNED #709" in content
    assert "RELATED #5731" in content
    assert "Dockerfile.base @\u200b 2.9.7" in content
    assert "official Home Assistant add-on" in messages[0]["content"]


def test_assess_http_error_returns_none(sample_raw, monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(ai.requests, "post",
                        lambda *a, **k: _Resp({"error": "nope"}, status=429))
    diag = parse_diagnostics(sample_raw)
    assert ai.assess(diag, "t", "b", token="x") is None


def test_assess_malformed_output_returns_none(sample_raw, monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    bad = {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(bad))
    diag = parse_diagnostics(sample_raw)
    assert ai.assess(diag, "t", "b", token="x") is None


def test_prompt_is_sanitized(injection_raw, monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    diag = parse_diagnostics(injection_raw)
    messages = ai.build_messages(diag, "title @x", "body", ["sonos"])
    blob = json.dumps(messages)
    assert "<script>" not in blob


def test_coerce_clamps_category(sample_raw, monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    payload = {"choices": [{"message": {"content": json.dumps({
        "summary": "s", "likely_root_cause": "rc", "category": "totally-made-up",
        "confidence": 5, "suggested_labels": "notalist", "user_message": "hi",
    })}}]}
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Resp(payload))
    diag = parse_diagnostics(sample_raw)
    result = ai.assess(diag, "t", "b", token="x")
    assert result.category == "unknown"        # unknown enum → clamped
    assert result.confidence == 1.0            # clamped into [0,1]
    assert result.suggested_labels == []       # non-list → empty
