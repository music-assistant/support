from ma_triage import comment, config
from ma_triage.analyze import analyze
from ma_triage.diagnostics import parse_diagnostics
from ma_triage.models import AIResult, TriageResult


def _actionable_result(sample_raw, fake_gh):
    diag = parse_diagnostics(sample_raw)
    findings, labels = analyze(diag, fake_gh)
    return TriageResult(
        has_diagnostics=True, findings=findings, labels_to_add=labels,
        diagnostics=diag, maintainers_to_ping={"SantiagoSotoC"},
    )


def test_build_body_actionable(sample_raw, fake_gh):
    result = _actionable_result(sample_raw, fake_gh)
    body = comment.build_body(result)
    assert config.STICKY_MARKER in body
    assert "Version:" in body
    assert config.DISCLOSURE_FOOTER.strip()[:10] in body
    assert "@SantiagoSotoC" in body  # maintainer ping


def test_build_body_missing_info():
    result = TriageResult(missing_sections=["The problem"])
    body = comment.build_body(result)
    assert "The problem" in body
    assert "Download diagnostics" in body


def test_build_body_invalid():
    result = TriageResult(diagnostics_invalid=True)
    body = comment.build_body(result)
    assert "couldn't read it" in body or "regenerate" in body


def test_build_body_screenshot_instead_of_diagnostics():
    # Main form, all sections filled, but a screenshot was pasted in the
    # diagnostics field instead of the actual file (issue #5815 pattern).
    result = TriageResult(
        form_kind="main",
        missing_attachment=True,
        has_media_attachment=True,
        missing_sections=[],
    )
    body = comment.build_body(result)
    assert "screenshot" in body.lower()
    assert "Download diagnostics" in body  # still points to the how-to


def test_build_body_no_attachment_no_screenshot():
    # No attachment at all → generic ask, and no misleading screenshot note.
    result = TriageResult(form_kind="main", missing_attachment=True)
    body = comment.build_body(result)
    assert "diagnostics report or log file" in body
    assert "screenshot" not in body.lower()


def test_build_body_frontend_missing():
    result = TriageResult(
        form_kind="frontend", missing_attachment=True, missing_sections=[]
    )
    body = comment.build_body(result)
    assert config.FRONTEND_MISSING_MESSAGE[:20] in body
    assert config.STICKY_MARKER in body


def test_build_body_log_source_note(sample_log, fake_gh):
    from ma_triage import analyze, logscan
    diag = logscan.scan_log(sample_log)
    findings, labels = analyze.analyze(diag, fake_gh)
    result = TriageResult(
        form_kind="main", has_diagnostics=True, findings=findings,
        labels_to_add=labels, diagnostics=diag,
    )
    body = comment.build_body(result)
    assert "attached log file" in body  # log-fallback note present
    assert "attached log" in body  # findings section wording
    # No raw secret leaks through the rendered comment.
    assert "/home/frank" not in body
    assert "sk-abcdef0123456789ABCDEF" not in body


def test_ai_section_rendered(sample_raw, fake_gh):
    result = _actionable_result(sample_raw, fake_gh)
    result.ai = AIResult(
        summary="Looks like a network hiccup.",
        likely_root_cause="Sonos device offline.",
        category="config", confidence=0.6,
    )
    body = comment.build_body(result)
    assert "AI assessment" in body
    assert "Sonos device offline." in body
    assert "60%" in body
    # rendered as a collapsed block for maintainers, not an always-open section
    assert "<details>" in body and "<summary>" in body
    assert "### 🤖 AI assessment" not in body


def test_state_roundtrip():
    state = {"v": 1, "has_diagnostics": True, "version": "2.8.0"}
    rendered = comment._render_state(state)
    parsed = comment.parse_state(f"some body\n\n{rendered}")
    assert parsed == state


def test_state_render_is_html_safe():
    rendered = comment._render_state({"x": "</script><b>"})
    assert "</script>" not in rendered
    assert "<b>" not in rendered


def test_upsert_creates_then_updates(fake_gh):
    result = TriageResult(missing_sections=["The problem"])
    body = comment.build_body(result)
    comment.upsert(fake_gh, 5, body, {"v": 1})
    assert any(c[0] == "create_comment" for c in fake_gh.calls)

    # second run finds the sticky and updates in place
    fake_gh.calls.clear()
    comment.upsert(fake_gh, 5, body, {"v": 2})
    assert any(c[0] == "update_comment" for c in fake_gh.calls)
    assert not any(c[0] == "create_comment" for c in fake_gh.calls)


def test_injection_body_has_no_live_mentions(injection_raw, fake_gh):
    result = _actionable_result(injection_raw, fake_gh)
    body = comment.build_body(result)
    assert "<script>" not in body
    assert "@maintainer" not in body


def test_injection_system_fields_cannot_forge_state(injection_raw, fake_gh):
    # A crafted system.version carries a fake state marker + @mention. It must be
    # neutralised, and must NOT be picked up as the bot's own state on re-read.
    result = _actionable_result(injection_raw, fake_gh)
    body = comment.build_body(result)
    assert "@everyone" not in body
    assert "<script>" not in body

    # Simulate the full sticky (body + real state) and confirm parse_state only
    # sees the genuine trailing state block, not the forged inline one.
    real_state = {"v": 1, "has_diagnostics": True}
    full = f"{body}\n\n{comment._render_state(real_state)}"
    assert comment.parse_state(full) == real_state


def test_ai_output_is_sanitized(sample_raw, fake_gh):
    result = _actionable_result(sample_raw, fake_gh)
    result.ai = AIResult(
        summary="call @everyone <!-- ma-triage-state:{\"x\":1} -->",
        likely_root_cause="ping @maintainer <script>x</script>",
        category="bug", confidence=0.5,
    )
    body = comment.build_body(result)
    assert "@everyone" not in body
    assert "@maintainer" not in body
    assert "<script>" not in body
    # a forged marker in AI text must not be parseable as real state
    full = f"{body}\n\n{comment._render_state({'ok': True})}"
    assert comment.parse_state(full) == {"ok": True}
