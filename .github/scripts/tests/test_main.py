from ma_triage import __main__ as main
from ma_triage import config
from ma_triage.models import AIResult, RagResult

MAIN_BODY_FULL = (
    "### What happened?\n\nIt crashes on startup\n\n"
    "### How to reproduce\n\nStart the server\n\n"
    "### Music Assistant version\n\n2.9.5\n\n"
    "### How do you run Music Assistant?\n\nHome Assistant add-on"
)


def test_build_result_actionable(sample_raw, fake_gh, monkeypatch):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: "http://x")
    monkeypatch.setattr(main, "download_capped", lambda url: sample_raw)
    result = main.build_result(fake_gh, "snapcast timeout", "body", token="t")
    assert result.is_actionable
    assert result.findings
    # A single explicitly-reported provider routes to its community codeowner.
    assert "SantiagoSotoC" in result.maintainers_to_ping


def test_build_result_uses_reported_provider_not_diagnostics_census(
    sample_raw, fake_gh, monkeypatch
):
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: "http://x")
    monkeypatch.setattr(main, "download_capped", lambda url: sample_raw)
    body = (
        "### What happened?\n\nFunkwhale via Subsonic returns 404; Sonos is fine.\n\n"
        "### How to reproduce\n\nOpen a Subsonic album.\n\n"
        "### Music Assistant version\n\n2.9.7\n\n"
        "### How do you run Music Assistant?\n\nHome Assistant add-on"
    )
    result = main.build_result(
        fake_gh,
        "Subsonic getLyrics returns 404",
        body,
        token="t",
        labels=["triage"],
    )
    assert result.reported_providers == {"subsonic"}
    assert "subsonic" in result.labels_to_add
    assert "sonos" not in result.labels_to_add
    assert "Chromecast" not in result.labels_to_add
    assert result.maintainers_to_ping == {"khers"}
    assert [doc.url for doc in result.provider_docs] == [
        "https://music-assistant.io/music-providers/subsonic/"
    ]


def test_build_result_assesses_after_retrieving_rag_and_code(
    sample_raw, fake_gh, monkeypatch
):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(main, "find_diagnostics_url", lambda body: "http://x")
    monkeypatch.setattr(main, "download_capped", lambda url: sample_raw)
    rag_result = RagResult(tier="low")
    monkeypatch.setattr(main.rag, "answer", lambda *args, **kwargs: rag_result)
    monkeypatch.setattr(
        main.code_context,
        "build",
        lambda *args, **kwargs: "SOURCE: helpers.py @ 2.9.7\nbundled binary",
    )
    captured = {}

    def assess(*args, **kwargs):
        captured.update(kwargs)
        return AIResult(
            summary="Packaging regression",
            likely_root_cause="Bundled binary missing",
            category="bug",
            confidence=0.9,
        )

    monkeypatch.setattr(main.ai, "assess", assess)
    result = main.build_result(
        fake_gh,
        "snapcast binary missing",
        MAIN_BODY_FULL,
        token="t",
        labels=["triage"],
    )
    assert captured["rag_result"] is rag_result
    assert "bundled binary" in captured["code_context"]
    assert result.ai is not None
    assert result.ai.category == "bug"


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


def test_models_token_prefers_secret(monkeypatch):
    monkeypatch.setenv("GH_MODELS_TOKEN", "pat-xyz")
    assert main._models_token("ghtok") == "pat-xyz"


def test_models_token_falls_back_when_unset_or_blank(monkeypatch):
    monkeypatch.delenv("GH_MODELS_TOKEN", raising=False)
    assert main._models_token("ghtok") == "ghtok"
    monkeypatch.setenv("GH_MODELS_TOKEN", "")
    assert main._models_token("ghtok") == "ghtok"


def test_apply_triage_state_labels_mutually_exclusive(fake_gh):
    from ma_triage.models import TriageResult
    # Existing issue already needs-attention; this pass -> waiting-for-user.
    issue = {"number": 42, "labels": [{"name": "needs-attention"}, {"name": "sonos"}]}
    result = TriageResult(form_kind="main", missing_sections=["What happened?"])
    main.apply_triage(fake_gh, 42, issue, result)
    added = [c for c in fake_gh.calls if c[0] == "add_labels"]
    assert any("waiting-for-user" in c[2] for c in added)
    # the opposite state label is removed rather than left to contradict
    assert ("remove_label", 42, "needs-attention") in fake_gh.calls


def test_apply_triage_keeps_state_when_unchanged(fake_gh):
    from ma_triage.models import TriageResult
    # Already waiting-for-user; a still-missing-info pass must not remove it.
    issue = {"number": 43, "labels": [{"name": "waiting-for-user"}]}
    result = TriageResult(form_kind="main", missing_sections=["What happened?"])
    main.apply_triage(fake_gh, 43, issue, result)
    assert not any(c[0] == "remove_label" for c in fake_gh.calls)


def test_state_records_the_whole_decision(monkeypatch, fake_gh):
    """Every claim the bot makes has to leave a trace that can be graded.

    GitHub records what an issue became; nothing records what the bot said about
    it. A field missing here is a capability that cannot be measured against the
    outcome afterwards.
    """
    from ma_triage.models import Finding, Severity, TriageResult

    result = TriageResult(
        form_kind="main",
        has_diagnostics=True,
        missing_sections=["How to reproduce"],
        missing_attachment=True,
        log_wall_detected=True,
        reported_providers={"sonos"},
        labels_to_add={"sonos", "bug"},
        maintainers_to_ping={"@someone"},
        findings=[Finding(severity=Severity.WARNING, title="Outdated version",
                          detail="d")],
    )
    captured: dict = {}
    monkeypatch.setattr(
        main.comment, "upsert",
        lambda gh, number, body, state: captured.update(state),
    )
    monkeypatch.setattr(main.comment, "build_body", lambda r: "body")
    monkeypatch.setattr(main, "_resolve_labels", lambda gh, r: [])
    main.apply_triage(fake_gh, 1, {"labels": []}, result)

    assert captured["v"] == 2
    assert captured["missing_sections"] == ["How to reproduce"]
    assert captured["missing_attachment"] is True
    assert captured["log_wall"] is True
    assert captured["labels"] == ["bug", "sonos"]
    assert captured["pinged"] == ["@someone"]
    assert captured["findings"] == ["Outdated version"]


# --- the gist fires only for reports long enough to need it -------------------- #
def _body_with_description(chars):
    return (
        f"### What happened?\n\n{'x' * chars}\n\n"
        "### How to reproduce\n\nDo the thing\n\n"
        "### Music Assistant version\n\n2.10.0\n\n"
        "### How do you run Music Assistant?\n\nHome Assistant add-on"
    )


def _gist_calls(monkeypatch, fake_gh, chars, *, ai_enabled=True):
    """How many gist calls `build_result` makes for a description of `chars`."""
    calls = []
    monkeypatch.setattr(config, "AI_ENABLED", ai_enabled)
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(
        main.ai, "summarise_report",
        lambda title, body, *, token: calls.append(title) or None,
    )
    main.build_result(fake_gh, "t", _body_with_description(chars), token="x")
    return len(calls)


def test_gist_is_skipped_for_a_report_short_enough_to_read(monkeypatch, fake_gh):
    assert _gist_calls(monkeypatch, fake_gh, config.GIST_MIN_CHARS - 1) == 0


def test_gist_fires_once_the_description_is_long(monkeypatch, fake_gh):
    assert _gist_calls(monkeypatch, fake_gh, config.GIST_MIN_CHARS) == 1


def test_gist_costs_nothing_when_ai_is_off(monkeypatch, fake_gh):
    assert _gist_calls(monkeypatch, fake_gh, 5000, ai_enabled=False) == 0


# --- recovering the form's answers from a report that replaced it -------------- #
_REPLACED = "# My bug\n\n## Environment\n\nMA 2.9.2, Docker\n\n## Detail\n\n" + "x" * 2000


def test_recovered_fields_only_ever_fill_a_blank(monkeypatch, fake_gh):
    """A form answer always beats a reading of one."""
    from ma_triage.models import ReportGist

    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(
        main.ai, "summarise_report",
        lambda title, body, *, token: ReportGist(
            doing="d", version="9.9.9", install_method="guessed"
        ),
    )
    # A replaced form has nothing to beat it, so the reading is used.
    res = main.build_result(fake_gh, "t", _REPLACED, token="x")
    assert res.reported_version == "9.9.9"
    assert res.install_method == "guessed"


def test_recovery_is_not_applied_when_the_form_was_used(monkeypatch, fake_gh):
    from ma_triage.models import ReportGist

    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(
        main.ai, "summarise_report",
        lambda title, body, *, token: ReportGist(doing="d", version="9.9.9"),
    )
    body = _body_with_description(config.GIST_MIN_CHARS)
    res = main.build_result(fake_gh, "t", body, token="x")
    assert res.form_replaced is False
    assert res.reported_version == "2.10.0"


def test_the_comment_asks_for_something_exactly_when_it_waits_for_the_user(
    monkeypatch, fake_gh
):
    """The ask and the `waiting-for-user` label must not decide separately.

    They did: recovery silenced the ask while `missing_sections` still held all
    four, so the bot requested nothing and the sweep then closed the issue for
    going unanswered.
    """
    from ma_triage import comment as comment_mod
    from ma_triage.models import ReportGist

    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(
        main.ai, "summarise_report",
        lambda title, body, *, token: ReportGist(
            doing="pressed play", happened="no sound",
            version="2.9.2", install_method="Docker",
        ),
    )
    replaced = "# Bug\n\n## Detail\n\n" + "x" * 2000
    result = main.build_result(fake_gh, "t", replaced, token="x")

    assert result.form_replaced and result.has_recovered_fields
    assert result.missing_sections == [], "recovered answers must clear their questions"

    body = comment_mod.build_body(result)
    # Recovery answered the form, so that ask is gone; the diagnostics file was
    # never in the report and is still wanted, so that one remains.
    assert config.FORM_REPLACED_NOTE not in body
    asks_for_something = "Could you attach" in body or config.FORM_REPLACED_NOTE in body
    assert asks_for_something is result.needs_user_action, (
        "the comment and the waiting-for-user label must agree: asking for "
        "nothing while waiting is what let the sweep close unanswered issues"
    )


def test_a_recovered_version_does_not_originate_a_label(monkeypatch, fake_gh):
    """The model may narrow the deterministic label set, never add to it."""
    from ma_triage.models import ReportGist

    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(
        main.ai, "summarise_report",
        lambda title, body, *, token: ReportGist(doing="d", happened="h", version="2.0.0"),
    )
    result = main.build_result(fake_gh, "t", "# Bug\n\n## Detail\n\n" + "x" * 2000, token="x")
    assert result.reported_version == "2.0.0"
    assert not any("outdated" in label for label in result.labels_to_add)

def test_gist_reaches_a_report_that_replaced_the_form(monkeypatch, fake_gh):
    """These have no "What happened?" section, so the old gate excluded them.

    They are the longest reports in the tracker and the ones a maintainer most
    needs condensed; keying on a section they do not have got that backwards.
    """
    calls = []
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", False)
    monkeypatch.setattr(
        main.ai, "summarise_report",
        lambda title, body, *, token: calls.append(title) or None,
    )
    own_headings = "# My bug\n\n## Environment\n\nMA 2.9.2, Docker\n\n## Detail\n\n" + "x" * 2000
    main.build_result(fake_gh, "t", own_headings, token="x")
    assert calls, "a report that replaced the form should still be condensed"
