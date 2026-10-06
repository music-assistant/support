import pytest
from conftest import FakeGH
from ma_triage import config
from ma_triage.gh import GitHubClient
from ma_triage.providers import (
    detect_provider_labels_from_text,
    detect_reported_provider_labels,
    domain_to_label,
    filter_existing_labels,
    load_manifests,
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


def test_youtube_music_resolves_current_manifest_metadata(fake_gh):
    fake_gh._manifests["ytmusic"] = {
        "name": "YouTube Music",
        "codeowners": ["@MarvinSchenkel"],
        "documentation": "https://music-assistant.io/music-providers/youtube-music/",
    }
    assert provider_manifest_domain("youtube_music") == "ytmusic"
    assert resolve_maintainers(fake_gh, "youtube_music") == ["MarvinSchenkel"]
    doc = resolve_provider_doc(fake_gh, "youtube_music")
    assert doc is not None
    assert doc.label == "youtube_music"
    assert doc.url == "https://music-assistant.io/music-providers/youtube-music/"


def test_spotify_connect_resolves_plugin_documentation(fake_gh):
    doc = resolve_provider_doc(fake_gh, "Spotify Connect")
    assert doc is not None
    assert doc.label == "Spotify Connect"
    assert doc.url == "https://music-assistant.io/plugins/spotify-connect/"


def test_provider_is_known_by_its_manifest_name(fake_gh):
    fake_gh._manifests["qqmusic"] = {"name": "QQ Music", "codeowners": ["@xiasi0"]}
    assert load_manifests(fake_gh)
    assert detect_reported_provider_labels(
        "QQ Music full-stream URL requests fail with 104003", ""
    ) == {"qqmusic"}
    assert resolve_maintainers(fake_gh, "qqmusic") == ["xiasi0"]


def test_manifest_name_in_the_title_wins_over_a_player_in_the_body(fake_gh):
    fake_gh._manifests["storytel"] = {"name": "Storytel", "codeowners": ["@jonasbp2011"]}
    load_manifests(fake_gh)
    body = "### How to reproduce\n\n1. Select a Google Cast player.\n2. Press Play."
    assert detect_reported_provider_labels(
        "Storytel/Mofibo audiobooks fail to stream", body
    ) == {"storytel"}


def test_manifest_name_matches_only_in_its_own_casing(fake_gh):
    fake_gh._manifests["audible"] = {"name": "Audible", "codeowners": ["@ztripez"]}
    load_manifests(fake_gh)
    assert detect_provider_labels_from_text("Audible: library titles not synced") == {"audible"}
    assert detect_provider_labels_from_text("an audible pop between tracks") == set()


def test_manifest_name_drops_its_generic_suffix(fake_gh):
    fake_gh._manifests["emby"] = {
        "name": "Emby Media Server Library",
        "codeowners": ["@hatharry"],
    }
    load_manifests(fake_gh)
    assert detect_provider_labels_from_text("Emby provider no longer syncing plays") == {"emby"}


def test_only_community_owned_providers_are_known_by_name(fake_gh):
    fake_gh._manifests["builtin"] = {"name": "Music Assistant", "codeowners": ["@music-assistant"]}
    fake_gh._manifests["_demo_music_provider"] = {
        "name": "Demo Music Provider",
        "codeowners": ["@yourgithubusername"],
    }
    load_manifests(fake_gh)
    assert detect_provider_labels_from_text("Music Assistant crashes on start") == set()
    assert detect_provider_labels_from_text("Demo Music Provider fails") == set()


def test_hand_written_alias_keeps_its_label_over_the_manifest_name(fake_gh):
    fake_gh._manifests["ytmusic"] = {"name": "YouTube Music", "codeowners": ["@MarvinSchenkel"]}
    load_manifests(fake_gh)
    assert detect_provider_labels_from_text("YouTube Music playback fails") == {"youtube_music"}


def test_unreadable_manifests_leave_the_hand_written_aliases(capsys):
    assert not load_manifests(FakeGH())
    assert "::error::" in capsys.readouterr().err
    assert detect_provider_labels_from_text("Spotify playback fails") == {"spotify"}


def test_subdirectory_files_are_read_in_two_requests(monkeypatch):
    client = GitHubClient("tok")
    sent = []

    def fake_graphql(query, variables=None, *, features=None):
        sent.append(query)
        if len(sent) == 1:
            entries = [
                {"name": "qqmusic", "type": "tree"},
                {"name": "storytel", "type": "tree"},
                {"name": "__init__.py", "type": "blob"},
            ]
            return {"data": {"repository": {"object": {"entries": entries}}}}
        return {"data": {"repository": {"f0": {"text": "{}"}, "f1": None}}}

    monkeypatch.setattr(client, "graphql", fake_graphql)
    files = client.get_subdirectory_files(
        "music-assistant/server", "music_assistant/providers", "manifest.json", ref="dev"
    )
    assert files == {"qqmusic": "{}"}  # storytel has no manifest.json
    assert len(sent) == 2
    assert '"dev:music_assistant/providers/storytel/manifest.json"' in sent[1]


@pytest.mark.parametrize("failing", [0, 1])
def test_subdirectory_files_are_none_when_an_error_left_them_partial(monkeypatch, failing):
    client = GitHubClient("tok")
    responses = [
        {"data": {"repository": {"object": {"entries": [{"name": "qqmusic", "type": "tree"}]}}}},
        {"data": {"repository": {"f0": {"text": "{}"}}}},
    ]
    responses[failing]["errors"] = [{"message": "timeout"}]
    monkeypatch.setattr(client, "graphql", lambda q, v=None, *, features=None: responses.pop(0))
    assert client.get_subdirectory_files("music-assistant/server", "p", "manifest.json") is None


def test_subdirectory_files_are_none_when_the_directory_is_unreadable(monkeypatch):
    client = GitHubClient("tok")
    monkeypatch.setattr(
        client,
        "graphql",
        lambda q, v=None, *, features=None: {"data": {"repository": {"object": None}}},
    )
    assert client.get_subdirectory_files("music-assistant/server", "nope", "manifest.json") is None


def test_provider_doc_rejects_external_url(fake_gh):
    fake_gh._manifests["evil"] = {
        "name": "Evil",
        "documentation": "https://evil.example/steal",
    }
    assert resolve_provider_doc(fake_gh, "evil") is None
