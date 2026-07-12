from ma_triage import config
from ma_triage.providers import (
    detect_provider_labels_from_text,
    detect_reported_provider_labels,
    domain_to_label,
    filter_existing_labels,
    provider_manifest_domain,
    resolve_maintainers,
    resolve_provider_doc,
)


def test_domain_to_label_known():
    assert domain_to_label("chromecast") == "Chromecast"
    assert domain_to_label("slimproto") == "Squeezelite"


def test_domain_to_label_fallback():
    assert domain_to_label("some_new_provider") == "some_new_provider"


def test_reported_provider_title_wins_over_incidental_body_mention():
    body = (
        "### What happened?\n\nFilesystem albums are marked new; Plex is fine.\n\n"
        "### How to reproduce\n\nOpen the filesystem album."
    )
    assert detect_reported_provider_labels(
        "Old filesystem albums marked as new", body
    ) == {"filesystem_local"}


def test_specific_spotify_connect_alias_wins_over_generic_spotify():
    assert detect_provider_labels_from_text(
        "Spotify Connect go-librespot error"
    ) == {"Spotify Connect"}
    assert provider_manifest_domain("Spotify Connect") == "spotify_connect"


def test_separate_spotify_and_spotify_connect_mentions_are_both_kept():
    assert detect_provider_labels_from_text(
        "Spotify playback works but Spotify Connect fails"
    ) == {"spotify", "Spotify Connect"}


def test_reported_provider_falls_back_to_form_body():
    body = "### What happened?\n\nFunkwhale via OpenSubsonic returns 404."
    assert detect_reported_provider_labels("Album page fails", body) == {"subsonic"}


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


def test_subsonic_resolves_current_manifest_metadata(fake_gh):
    assert provider_manifest_domain("subsonic") == "opensubsonic"
    assert resolve_maintainers(fake_gh, "subsonic") == ["khers"]
    doc = resolve_provider_doc(fake_gh, "subsonic")
    assert doc is not None
    assert doc.name == "OpenSubsonic Media Server Library"
    assert doc.url == "https://music-assistant.io/music-providers/subsonic/"


def test_spotify_connect_resolves_plugin_documentation(fake_gh):
    doc = resolve_provider_doc(fake_gh, "Spotify Connect")
    assert doc is not None
    assert doc.label == "Spotify Connect"
    assert doc.url == "https://music-assistant.io/plugins/spotify-connect/"


def test_provider_doc_rejects_external_url(fake_gh):
    fake_gh._manifests["evil"] = {
        "name": "Evil",
        "documentation": "https://evil.example/steal",
    }
    assert resolve_provider_doc(fake_gh, "evil") is None
