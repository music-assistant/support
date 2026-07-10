"""Tests for the raw-log fallback scanner (redact-first, derive facts)."""

from ma_triage import analyze, logscan


def test_redaction_removes_secrets_and_pii(sample_log):
    redacted = logscan.redact(sample_log.decode())
    # Secrets / tokens
    assert "sk-abcdef0123456789ABCDEF" not in redacted
    assert "super-secret-value-1234" not in redacted
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    # Home directory, email, MAC, public IP
    assert "/home/frank" not in redacted
    assert "frank@example.com" not in redacted
    assert "aa:bb:cc:dd:ee:ff" not in redacted
    assert "8.8.8.8" not in redacted
    # Private IP is kept (useful, not sensitive)
    assert "192.168.1.50" in redacted


def test_scan_log_extracts_version_and_safe_mode(sample_log):
    diag = logscan.scan_log(sample_log)
    assert diag.source == "log"
    assert diag.system.version == "2.8.1"
    assert diag.system.safe_mode is True


def test_scan_log_groups_exceptions_by_fingerprint(sample_log):
    diag = logscan.scan_log(sample_log)
    types = {e.exc_type for e in diag.exceptions}
    assert "ValueError" in types
    assert "ConnectionResetError" in types
    # The two ValueErrors differ only by a number → same fingerprint, count 2.
    value_error = next(e for e in diag.exceptions if e.exc_type == "ValueError")
    assert value_error.count == 2
    # Most frequent first.
    assert diag.exceptions[0].count >= diag.exceptions[-1].count


def test_scan_log_detects_provider_errors(sample_log):
    diag = logscan.scan_log(sample_log)
    domains = {p.domain for p in diag.providers}
    assert "sonos" in domains
    assert "spotify" in domains
    assert all(p.in_error for p in diag.providers)


def test_log_diag_flows_through_analyze(sample_log, fake_gh):
    diag = logscan.scan_log(sample_log)
    findings, labels = analyze.analyze(diag, fake_gh)
    titles = " ".join(f.title.lower() for f in findings)
    assert "safe mode" in titles
    assert "exception" in titles
    assert "error state" in titles
    # 2.8.1 is older than the fake latest (2.9.5)
    assert any("outdated" in f.title.lower() for f in findings)


def test_redacted_facts_only_no_raw_secret_in_findings(sample_log, fake_gh):
    diag = logscan.scan_log(sample_log)
    findings, _ = analyze.analyze(diag, fake_gh)
    blob = "\n".join(f.detail for f in findings)
    assert "sk-abcdef0123456789ABCDEF" not in blob
    assert "/home/frank" not in blob
    assert "frank@example.com" not in blob
