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


# --- chat transport --------------------------------------------------------- #
def test_strip_fence_unwraps_a_fenced_json_block():
    """A backend without `response_format` tends to fence its answer."""
    assert ai._strip_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert ai._strip_fence('```\n{"a": 1}\n```') == '{"a": 1}'
    assert ai._strip_fence('{"a": 1}') == '{"a": 1}'
    assert ai._strip_fence('  {"a": 1}  ') == '{"a": 1}'


def test_chat_returns_none_and_names_the_caller_on_failure(monkeypatch, capsys):
    """A silent or mislabelled skip is what hid a dead provider for 16 days."""
    monkeypatch.setattr(
        ai.requests, "post", lambda *a, **k: _Resp({"error": "nope"}, status=503)
    )
    assert ai._chat({}, token="t", what="Doc-answer judge") is None
    assert "Doc-answer judge skipped: HTTP 503" in capsys.readouterr().out


def test_chat_rejects_a_non_object_response(monkeypatch):
    """Callers index the result like a mapping; a bare list must not reach them."""
    monkeypatch.setattr(
        ai.requests,
        "post",
        lambda *a, **k: _Resp({"choices": [{"message": {"content": "[1, 2]"}}]}),
    )
    assert ai._chat({}, token="t", what="AI assessment") is None


# --- CLI backend (GitHub Copilot) -------------------------------------------- #
def _payload(schema=None):
    p = {"model": "m", "messages": [
        {"role": "system", "content": "you are a triage assistant"},
        {"role": "user", "content": "ISSUE BODY --not-a-flag"},
    ]}
    if schema:
        p["response_format"] = {"type": "json_schema",
                                "json_schema": {"schema": schema}}
    return p


def test_prompt_from_carries_the_schema_as_instructions():
    """`response_format` has no CLI equivalent, so the schema has to be asked for."""
    text = ai._prompt_from(_payload({"type": "object", "required": ["summary"]}))
    assert "you are a triage assistant" in text
    assert "ISSUE BODY" in text
    assert "JSON Schema" in text and '"required":["summary"]' in text


def test_chat_via_cli_sends_the_prompt_on_stdin_not_argv(monkeypatch):
    """Issue text is written by anyone, and argv is readable from the process
    table by every other step in the job."""
    monkeypatch.setattr(config, "AI_CLI_TOKEN", "tok")
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["input"] = kwargs.get("input")
        seen["env"] = kwargs.get("env")
        class R:
            returncode = 0
            stdout = '```json\n{"answers_question": true}\n```'
            stderr = ""
        return R()

    monkeypatch.setattr(ai.subprocess, "run", fake_run)
    assert ai._chat(_payload(), token="unused", what="X") == {"answers_question": True}
    assert seen["args"] == ["copilot", "-s", "--no-ask-user"]
    assert not any("ISSUE BODY" in a for a in seen["args"])
    assert "ISSUE BODY" in seen["input"]
    # Passed explicitly: the CLI finds its own credentials otherwise, and
    # authenticating as something else silently is worse than failing.
    assert seen["env"]["COPILOT_GITHUB_TOKEN"] == "tok"


def test_chat_via_cli_skips_on_a_non_zero_exit(monkeypatch, capsys):
    monkeypatch.setattr(config, "AI_CLI_TOKEN", "tok")

    class R:
        returncode = 1
        stdout = ""
        stderr = "Access denied by policy settings"

    monkeypatch.setattr(ai.subprocess, "run", lambda *a, **k: R())
    assert ai._chat(_payload(), token="unused", what="Doc-answer judge") is None
    assert "Access denied by policy settings" in capsys.readouterr().out


def test_chat_via_cli_skips_when_the_reply_is_not_json(monkeypatch, capsys):
    """Losing schema enforcement means prose is possible; it must not raise."""
    monkeypatch.setattr(config, "AI_CLI_TOKEN", "tok")

    class R:
        returncode = 0
        stdout = "I think the issue is probably a network problem."
        stderr = ""

    monkeypatch.setattr(ai.subprocess, "run", lambda *a, **k: R())
    assert ai._chat(_payload(), token="unused", what="AI assessment") is None
    assert "was not JSON" in capsys.readouterr().out


def test_chat_uses_http_when_no_cli_token_is_present(monkeypatch):
    monkeypatch.setattr(config, "AI_CLI_TOKEN", "")
    monkeypatch.setattr(
        ai.requests, "post",
        lambda *a, **k: _Resp({"choices": [{"message": {"content": '{"ok": 1}'}}]}),
    )
    assert ai._chat(_payload(), token="t", what="X") == {"ok": 1}
