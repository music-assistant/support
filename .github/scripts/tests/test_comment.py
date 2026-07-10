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
