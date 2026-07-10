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


def test_redaction_covers_url_creds_base64_and_ipv6():
    raw = (
        "connecting to https://admin:hunter2@example.com/api\n"
        "api_key=ZmFrZS9rZXkrdmFsdWU9PQ==\n"
        "remote peer 2606:4700:4700::1111 responded\n"
        "local peer fe80::1 and ::1 are fine\n"
    )
    out = logscan.redact(raw)
    # URL basic-auth creds stripped (host kept)
    assert "hunter2" not in out
    assert "admin:hunter2@" not in out
    assert "example.com" in out
    # base64 secret value redacted in full (no trailing fragment survives)
    assert "ZmFrZS9rZXkrdmFsdWU9PQ==" not in out
    assert "dmFsdWU9PQ==" not in out
    # public IPv6 redacted, link-local / loopback kept
    assert "2606:4700:4700::1111" not in out
    assert "fe80::1" in out
    assert "::1 are fine" in out


def test_chained_exception_counts_once_as_final_type():
    log_text = (
        "Traceback (most recent call last):\n"
        '  File "a.py", line 1, in f\n'
        "    g()\n"
        "KeyError: 'x'\n"
        "\n"
        "During handling of the above exception, another exception occurred:\n"
        "\n"
        "Traceback (most recent call last):\n"
        '  File "b.py", line 2, in h\n'
        "    boom()\n"
        "RuntimeError: wrapped failure\n"
        "2024-05-01 12:00:00 INFO [mass] back to normal logging\n"
    )
    diag = logscan.scan_log(log_text)
    types = [e.exc_type for e in diag.exceptions]
    # One fingerprint, represented by the FINAL exception (not split in two).
    assert types == ["RuntimeError"]
    assert diag.exceptions[0].count == 1


def test_custom_exception_type_not_dropped():
    log_text = (
        "Traceback (most recent call last):\n"
        '  File "a.py", line 1, in f\n'
        "    g()\n"
        "InvalidState: provider not ready\n"
        "2024-05-01 12:00:00 INFO [mass] next line\n"
    )
    diag = logscan.scan_log(log_text)
    assert [e.exc_type for e in diag.exceptions] == ["InvalidState"]
