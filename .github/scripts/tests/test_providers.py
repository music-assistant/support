from ma_triage import config
from ma_triage.providers import (
    domain_to_label,
    filter_existing_labels,
    resolve_maintainers,
)


def test_domain_to_label_known():
    assert domain_to_label("chromecast") == "Chromecast"
    assert domain_to_label("slimproto") == "Squeezelite"


def test_domain_to_label_fallback():
    assert domain_to_label("some_new_provider") == "some_new_provider"


def test_filter_existing_case_insensitive():
    kept = filter_existing_labels({"chromecast", "sonos", "nope"},
                                  {"Chromecast", "sonos"})
    assert kept == {"Chromecast", "sonos"}


def test_resolve_maintainers_skips_core_team(fake_gh):
    # sonos manifest only lists the core team → no community maintainer.
    assert resolve_maintainers(fake_gh, "sonos") == []


def test_resolve_maintainers_community(fake_gh):
    handles = resolve_maintainers(fake_gh, "snapcast")
    assert handles == ["SantiagoSotoC"]


def test_resolve_maintainers_unknown(fake_gh):
    assert resolve_maintainers(fake_gh, "does_not_exist") == []
