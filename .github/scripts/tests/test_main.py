from ma_triage import __main__ as main
from ma_triage import config


def test_build_result_actionable(sample_raw, fake_gh, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: "http://x")
    monkeypatch.setattr(main, "download_capped", lambda url: sample_raw)
    result = main.build_result(fake_gh, "title", "body", token="t")
    assert result.is_actionable
    assert result.findings
    # snapcast community maintainer surfaced (sonos is core-team only)
    assert "SantiagoSotoC" in result.maintainers_to_ping


def test_build_result_no_diagnostics(fake_gh, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: None)
    result = main.build_result(fake_gh, "title", "body", token="t")
    assert not result.is_actionable
    assert not result.has_diagnostics


def test_build_result_invalid_download(fake_gh, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: "http://x")
    monkeypatch.setattr(main, "download_capped", lambda url: None)
    result = main.build_result(fake_gh, "title", "body", token="t")
    assert result.diagnostics_invalid is True
    assert not result.is_actionable


def test_resolve_labels_filters_to_existing(sample_raw, fake_gh, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: "http://x")
    monkeypatch.setattr(main, "download_capped", lambda url: sample_raw)
    result = main.build_result(fake_gh, "title", "body", token="t")
    labels = main._resolve_labels(fake_gh, result)
    # only labels that exist in the fake repo survive
    assert set(labels).issubset(fake_gh.list_labels())
    assert config.LABEL_NEEDS_ATTENTION in labels


def test_resolve_labels_needs_diagnostics_when_missing(fake_gh):
    from ma_triage.models import TriageResult
    result = TriageResult(missing_sections=["The problem"])
    labels = main._resolve_labels(fake_gh, result)
    assert config.LABEL_WAITING_FOR_USER in labels
    assert config.LABEL_NEEDS_DIAGNOSTICS in labels
