from ma_triage import analyze, config
from ma_triage.diagnostics import parse_diagnostics
from ma_triage.models import Severity


def test_analyze_sample(sample_raw, fake_gh):
    diag = parse_diagnostics(sample_raw)
    findings, labels = analyze.analyze(diag, fake_gh)
    titles = [f.title for f in findings]

    assert "Outdated version" in titles
    assert any("error state" in t for t in titles)
    assert any("exception" in t.lower() for t in titles)
    assert any("disk" in t.lower() for t in titles)  # free_mb 128 < 256

    # critical findings sort first
    assert findings[0].severity == Severity.CRITICAL

    # The diagnostics census describes the whole installation and must not label
    # every configured provider/player. Setup + version labels are still useful.
    assert "sonos" not in labels
    assert "Chromecast" not in labels
    assert "hass" in labels


def test_safe_mode_flagged(injection_raw, fake_gh):
    diag = parse_diagnostics(injection_raw)
    findings, _ = analyze.analyze(diag, fake_gh)
    assert any("safe mode" in f.title.lower() for f in findings)


def test_error_strings_are_sanitized(injection_raw, fake_gh):
    diag = parse_diagnostics(injection_raw)
    findings, _ = analyze.analyze(diag, fake_gh)
    blob = "\n".join(f.detail for f in findings)
    # the crafted provider error must not carry a live mention or raw HTML
    assert "<script>" not in blob
    assert "@maintainer" not in blob  # zero-width space inserted


def test_no_findings_when_clean(fake_gh):
    diag = parse_diagnostics(
        b'{"schema_version":1,"system":{"version":"2.9.5","safe_mode":false}}'
    )
    findings, labels = analyze.analyze(diag, fake_gh)
    # current version, no providers, no exceptions → no findings
    assert findings == []
