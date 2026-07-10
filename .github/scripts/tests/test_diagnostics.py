from ma_triage import diagnostics
from ma_triage.diagnostics import InvalidDiagnostics, parse_diagnostics, try_parse

import pytest


def test_parse_valid(sample_raw):
    diag = parse_diagnostics(sample_raw)
    assert diag.schema_version == 1
    assert diag.system.version == "2.8.0"
    assert diag.system.hass_addon is True
    assert diag.system.safe_mode is False
    # exceptions sorted most-frequent first
    assert diag.exceptions[0].count == 42
    assert len(diag.providers_in_error) == 2


def test_malformed_json_raises():
    with pytest.raises(InvalidDiagnostics):
        parse_diagnostics(b"{not json")


def test_non_object_top_level():
    with pytest.raises(InvalidDiagnostics):
        parse_diagnostics(b"[1,2,3]")


def test_missing_schema_version():
    with pytest.raises(InvalidDiagnostics):
        parse_diagnostics(b'{"system": {}}')


def test_missing_system():
    with pytest.raises(InvalidDiagnostics):
        parse_diagnostics(b'{"schema_version": 1}')


def test_depth_guard():
    payload = "{\"schema_version\":1,\"system\":{}," + '"a":' * 100 + "1" + "}" * 100
    with pytest.raises(InvalidDiagnostics):
        parse_diagnostics(payload.encode())


def test_try_parse_returns_none_on_bad():
    assert try_parse(b"nope") is None


def test_injection_values_preserved_as_data(injection_raw):
    diag = parse_diagnostics(injection_raw)
    # The parser keeps raw strings; escaping happens only at render time.
    assert "@maintainer" in diag.providers[0].last_error
    assert diag.system.safe_mode is True
