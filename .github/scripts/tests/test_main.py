from ma_triage import __main__ as main
from ma_triage import config

MAIN_BODY_FULL = (
    "### What happened?\n\nIt crashes on startup\n\n"
    "### How to reproduce\n\nStart the server\n\n"
    "### Music Assistant version\n\n2.9.5\n\n"
    "### How do you run Music Assistant?\n\nHome Assistant add-on"
)


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
    result = main.build_result(
        fake_gh, "title", MAIN_BODY_FULL, token="t", labels=["triage"]
    )
    labels = main._resolve_labels(fake_gh, result)
    # only labels that exist in the fake repo survive
    assert set(labels).issubset(fake_gh.list_labels())
    assert config.LABEL_NEEDS_ATTENTION in labels


def test_resolve_labels_needs_diagnostics_when_missing(fake_gh):
    from ma_triage.models import TriageResult
    result = TriageResult(missing_sections=["What happened?"])
    labels = main._resolve_labels(fake_gh, result)
    assert config.LABEL_WAITING_FOR_USER in labels
    assert config.LABEL_NEEDS_DIAGNOSTICS in labels


def test_valid_diagnostics_but_missing_section_waits_for_user(
    sample_raw, fake_gh, monkeypatch
):
    # Valid diagnostics attached, but the required "What happened?" is empty:
    # the reporter still owes us info, so state = waiting-for-user (not attention).
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: "http://x")
    monkeypatch.setattr(main, "download_capped", lambda url: sample_raw)
    body = (
        "### What happened?\n\n_No response_\n\n"
        "### How to reproduce\n\nStart it\n\n"
        "### Music Assistant version\n\n2.9.5\n\n"
        "### How do you run Music Assistant?\n\nHome Assistant add-on"
    )
    result = main.build_result(fake_gh, "t", body, token="t", labels=["triage"])
    assert result.is_actionable  # we can still diagnose
    assert result.needs_user_action  # but info is missing
    labels = main._resolve_labels(fake_gh, result)
    assert config.LABEL_WAITING_FOR_USER in labels
    assert config.LABEL_NEEDS_ATTENTION not in labels
    # diagnostics were provided, so don't nag for diagnostics specifically
    assert config.LABEL_NEEDS_DIAGNOSTICS not in labels


# --------------------------------------------------------------------------- #
# Form-kind branching
# --------------------------------------------------------------------------- #
FRONTEND_BODY = (
    "### Music Assistant version\n\n2.9.5\n\n"
    "### Browser and operating system\n\nFirefox on Linux\n\n"
    "### What happened?\n\nThe settings screen is blank\n\n"
    "### How to reproduce\n\nOpen settings"
)


def test_build_result_translation_is_skipped(fake_gh):
    result = main.build_result(
        fake_gh, "add German", "body", token="t", labels=["triage", "translation"]
    )
    assert result.skip is True
    assert result.form_kind == "translation"
    assert result.should_comment is False


def test_build_result_frontend_missing_media(fake_gh):
    result = main.build_result(
        fake_gh, "UI blank", FRONTEND_BODY, token="t", labels=["triage", "frontend"]
    )
    assert result.form_kind == "frontend"
    assert result.missing_attachment is True
    assert result.needs_user_action is True
    assert result.should_comment is True


def test_build_result_frontend_complete_is_silent(fake_gh):
    body = (
        FRONTEND_BODY
        + "\n\n![shot](https://github.com/user-attachments/assets/"
        "2b7c1f42-9a3e-4c1a-bb0a-1d2e3f4a5b6c)"
    )
    result = main.build_result(
        fake_gh, "UI blank", body, token="t", labels=["triage", "frontend"]
    )
    assert result.missing_attachment is False
    assert result.missing_sections == []
    assert result.should_comment is False


def test_build_result_log_fallback(fake_gh, sample_log, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: None)
    monkeypatch.setattr(
        main, "find_log_urls",
        lambda body: ["https://github.com/user-attachments/files/1/server.log"],
    )
    monkeypatch.setattr(
        main, "download_log_windowed", lambda url, **k: sample_log.decode()
    )
    body = (
        "### What happened?\n\nCrashes\n\n### How to reproduce\n\nStart it\n\n"
        "### Music Assistant version\n\n2.8.1\n\n"
        "### How do you run Music Assistant?\n\nDocker container"
    )
    result = main.build_result(fake_gh, "crash", body, token="t", labels=["triage"])
    assert result.is_actionable
    assert result.diagnostics is not None
    assert result.diagnostics.source == "log"
    assert any("exception" in f.title.lower() for f in result.findings)
    # Log-derived provider names must NOT ping maintainers.
    assert result.maintainers_to_ping == set()


def test_build_result_provider_labels_from_text(fake_gh, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: None)
    monkeypatch.setattr(main, "find_log_urls", lambda body: [])
    body = (
        "### What happened?\n\nSpotify playback keeps stopping\n\n"
        "### How to reproduce\n\nPlay any track\n\n"
        "### Music Assistant version\n\n2.9.5\n\n"
        "### How do you run Music Assistant?\n\nHome Assistant add-on"
    )
    result = main.build_result(fake_gh, "playback", body, token="t", labels=["triage"])
    assert "spotify" in result.labels_to_add
    assert result.missing_attachment is True


def test_build_result_unsupported_install_flagged(fake_gh, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: None)
    monkeypatch.setattr(main, "find_log_urls", lambda body: [])
    body = (
        "### What happened?\n\nBroken\n\n### How to reproduce\n\nRun\n\n"
        "### Music Assistant version\n\n2.9.5\n\n"
        "### How do you run Music Assistant?\n\nOther (unsupported)"
    )
    result = main.build_result(fake_gh, "x", body, token="t", labels=["triage"])
    assert any("unsupported" in f.title.lower() for f in result.findings)
