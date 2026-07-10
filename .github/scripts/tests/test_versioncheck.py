from ma_triage import config
from ma_triage.versioncheck import evaluate, parse_version


def test_parse_stable():
    v = parse_version("2.9.5")
    assert (v.major, v.minor, v.patch) == (2, 9, 5)
    assert not v.is_prerelease


def test_parse_beta():
    v = parse_version("2.10.0b4")
    assert v.is_prerelease
    assert v.pre_kind == "b" and v.pre_num == 4


def test_parse_dev():
    v = parse_version("2.10.0.dev2026070805")
    assert v.is_prerelease
    assert v.dev == 2026070805


def test_parse_with_v_prefix():
    assert parse_version("v2.9.5").patch == 5


def test_parse_garbage():
    assert parse_version("not-a-version") is None
    assert parse_version(None) is None


def test_ordering():
    assert parse_version("2.9.4") < parse_version("2.9.5")
    assert parse_version("2.10.0b1") < parse_version("2.10.0")
    assert parse_version("2.9.5") < parse_version("2.10.0")


def test_evaluate_outdated(fake_gh):
    verdict = evaluate("2.8.0", fake_gh)
    assert verdict.outdated is True
    assert verdict.latest_stable == "2.9.5"


def test_evaluate_current_not_outdated(fake_gh):
    verdict = evaluate("2.9.5", fake_gh)
    assert verdict.outdated is False


def test_evaluate_prerelease(fake_gh):
    verdict = evaluate("2.10.0b1", fake_gh)
    assert verdict.prerelease is True
    # newer than latest stable → not "outdated"
    assert verdict.outdated is False
