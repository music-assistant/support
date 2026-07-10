from ma_triage import config, copilot
from ma_triage.diagnostics import parse_diagnostics
from ma_triage.models import AIResult, TriageResult


def _result(sample_raw):
    diag = parse_diagnostics(sample_raw)
    return TriageResult(has_diagnostics=True, diagnostics=diag)


def test_dispatch_requires_token(sample_raw, fake_gh):
    outcome = copilot.dispatch(fake_gh, {"number": 1}, _result(sample_raw), token=None)
    assert outcome.dispatched is False
    assert "no COPILOT_DISPATCH_TOKEN" in outcome.reason


def test_dispatch_skips_when_agent_unavailable(sample_raw, fake_gh, monkeypatch):
    monkeypatch.setattr(copilot, "agent_available", lambda *a, **k: False)
    outcome = copilot.dispatch(fake_gh, {"number": 1}, _result(sample_raw), token="t")
    assert outcome.dispatched is False
    assert "not available" in outcome.reason


def test_dispatch_dry_run(sample_raw, fake_gh, monkeypatch):
    monkeypatch.setattr(copilot, "agent_available", lambda *a, **k: True)
    fake_gh.dry_run = True
    outcome = copilot.dispatch(fake_gh, {"number": 1}, _result(sample_raw), token="t")
    assert outcome.dispatched is False
    assert outcome.reason == "dry-run"


def test_dispatch_live(sample_raw, fake_gh, monkeypatch):
    monkeypatch.setattr(copilot, "agent_available", lambda *a, **k: True)

    class _Resp:
        status_code = 201
        content = b"{}"

        def json(self):
            return {"html_url": "https://github.com/x/y/pull/1",
                    "pull_request": {"html_url": "https://github.com/x/y/pull/1"}}

    monkeypatch.setattr(copilot.requests, "post", lambda *a, **k: _Resp())
    fake_gh.dry_run = False
    outcome = copilot.dispatch(fake_gh, {"number": 1}, _result(sample_raw), token="t")
    assert outcome.dispatched is True
    assert outcome.pr_url.endswith("/pull/1")


def test_should_auto_dispatch_gating(sample_raw, monkeypatch):
    result = _result(sample_raw)
    monkeypatch.setattr(config, "COPILOT_AUTO", False)
    assert copilot.should_auto_dispatch(result) is False

    monkeypatch.setattr(config, "COPILOT_AUTO", True)
    assert copilot.should_auto_dispatch(result) is False  # no AI result

    result.ai = AIResult(summary="", likely_root_cause="", category="bug",
                         confidence=0.9)
    assert copilot.should_auto_dispatch(result) is True

    result.ai.confidence = 0.1
    assert copilot.should_auto_dispatch(result) is False


def test_build_prompt_sanitized(injection_raw):
    result = _result(injection_raw)
    prompt = copilot.build_prompt({"number": 1, "title": "hi @x"}, result)
    assert "<script>" not in prompt
    assert "@maintainer" not in prompt
