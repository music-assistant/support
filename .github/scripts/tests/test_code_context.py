"""Tests for bounded official server-code evidence retrieval."""

from conftest import FakeGH
from ma_triage import code_context, config
from ma_triage.models import Diagnostics, ExceptionEntry, SystemInfo


def _diagnostics(*, origin=None, message="go-librespot binary not found on PATH"):
    exceptions = []
    if origin:
        exceptions.append(
            ExceptionEntry(
                exc_type="RuntimeError",
                fingerprint="x",
                count=1,
                message=message,
                origin=origin,
            )
        )
    return Diagnostics(
        schema_version=1,
        generated_at=None,
        system=SystemInfo(version="2.9.7", hass_addon=True),
        exceptions=exceptions,
    )


def _tree(*paths):
    """A git tree listing, which is how provider files are discovered."""
    return [{"path": path, "type": "blob"} for path in paths]


def test_build_retrieves_provider_and_packaging_evidence():
    gh = FakeGH(
        tree=_tree(
            "music_assistant/providers/spotify_connect/__init__.py",
            "music_assistant/providers/spotify_connect/helpers.py",
        ),
        raw_files={
            "music_assistant/providers/spotify_connect/helpers.py": (
                "def get_go_librespot_binary():\n"
                "    # Official Docker and Home Assistant images install it automatically.\n"
                "    raise RuntimeError('go-librespot binary not found on PATH')\n"
            ),
            "Dockerfile.base": (
                "ARG GO_LIBRESPOT_VERSION=0.7.4\n"
                "RUN install /tmp/go-librespot /usr/local/bin/go-librespot\n"
            ),
        }
    )
    evidence = code_context.build(
        gh,
        title="Spotify Connect go-librespot error",
        body="The go-librespot binary is not found on PATH after updating.",
        diagnostics=_diagnostics(),
        provider_labels={"Spotify Connect"},
        version="2.9.7",
    )
    assert "music_assistant/providers/spotify_connect/helpers.py @ 2.9.7" in evidence
    assert "Official Docker and Home Assistant images install it automatically" in evidence
    assert "Dockerfile.base @ 2.9.7" in evidence
    assert "GO_LIBRESPOT_VERSION=0.7.4" in evidence
    assert len(evidence) <= config.MAX_CODE_CONTEXT_CHARS


def test_build_uses_diagnostics_origin_path_without_provider():
    path = "music_assistant/controllers/players/controller.py"
    gh = FakeGH(
        raw_files={
            path: (
                "def register_player():\n"
                "    raise AlreadyRegisteredError('player already registered')\n"
            )
        }
    )
    evidence = code_context.build(
        gh,
        title="Player already registered",
        body="Registration fails",
        diagnostics=_diagnostics(
            origin=f"{path}:1509 in register",
            message="player already registered",
        ),
        provider_labels=set(),
        version="2.9.7",
    )
    assert path in evidence
    assert "AlreadyRegisteredError" in evidence


_SONOS = "music_assistant/providers/sonos/player.py"
_HASS = "music_assistant/providers/hass/__init__.py"


def _noisy_diagnostics():
    """A report-matching exception beside an unrelated background failure.

    The two tracebacks share only frame boilerplate — "File", "line" and a
    common frame — which is what every Python traceback has in common.
    """
    return Diagnostics(
        schema_version=1,
        generated_at=None,
        system=SystemInfo(version="2.9.7"),
        exceptions=[
            ExceptionEntry(
                exc_type="ConnectionError",
                fingerprint="a",
                count=5,
                message="sonos speaker disconnect during playback",
                origin=f"{_SONOS}:88 in _handle_playback",
                traceback=(
                    f'File "{_SONOS}", line 88, in _handle_playback\n'
                    "    await self._run()"
                ),
            ),
            ExceptionEntry(
                exc_type="SetupFailedError",
                fingerprint="b",
                count=1,
                message="error loading provider Home Assistant supervisor websocket 502",
                origin=f"{_HASS}:272 in handle_async_init",
                traceback=(
                    f'File "{_HASS}", line 272, in handle_async_init\n'
                    "    await self._run()"
                ),
            ),
        ],
    )


def _noisy_gh():
    return FakeGH(
        raw_files={
            _SONOS: (
                "async def _handle_playback(self):\n"
                "    # Speakers drop out when the subscription lapses.\n"
                "    raise ConnectionError('sonos speaker disconnect during playback')\n"
            ),
            _HASS: (
                "async def handle_async_init(self):\n"
                "    # Mirror Home Assistant playback state into the library.\n"
                "    raise SetupFailedError('supervisor websocket 502')\n"
            ),
        }
    )


def test_build_ignores_unrelated_background_exception_paths():
    """One matching exception must not vouch for the noise beside it."""
    gh = _noisy_gh()

    evidence = code_context.build(
        gh,
        title="Speakers keep dropping out during playback",
        body="My speakers disconnect mid playback and reappear seconds later.",
        diagnostics=_noisy_diagnostics(),
        provider_labels=set(),
        version="2.9.7",
    )

    assert _SONOS in evidence
    assert _HASS not in evidence
    # The fetch itself is the unconditional cost: an irrelevant file consumes a
    # request and a slot in the budget even when it later scores zero.
    assert _HASS not in gh.raw_reads


def test_build_keeps_reported_provider_paths_without_shared_vocabulary():
    """A path under a reported provider stands on the label, not on wording."""
    gh = _noisy_gh()

    evidence = code_context.build(
        gh,
        title="Sonos speakers keep dropping out",
        body="They disconnect and come back a few seconds later.",
        diagnostics=_noisy_diagnostics(),
        provider_labels={"sonos"},
        version="2.9.7",
    )

    assert _SONOS in evidence
    assert _HASS not in evidence


def test_build_finds_provider_modules_by_listing_the_directory():
    """Providers name their own modules; the directory is the only authority."""
    parsers = "music_assistant/providers/opensubsonic/parsers.py"
    gh = FakeGH(
        tree=_tree(
            "music_assistant/providers/opensubsonic/__init__.py",
            parsers,
        ),
        raw_files={
            parsers: (
                "def parse_track(item):\n"
                "    # Cover art id is optional in the Subsonic response.\n"
                "    return Track(image=item.get('coverArt'))\n"
            )
        },
    )

    evidence = code_context.build(
        gh,
        title="Track cover art missing in playlist view",
        body="The coverArt image never loads for tracks in a playlist.",
        diagnostics=_diagnostics(message="cover art missing"),
        provider_labels={"subsonic"},
        version="2.9.7",
    )

    assert parsers in evidence


def test_build_bounds_how_many_provider_files_it_will_fetch():
    """A directory listing is unbounded; the fetch budget is not."""
    many = [
        f"music_assistant/providers/opensubsonic/mod{index:02d}.py"
        for index in range(30)
    ]
    gh = FakeGH(tree=_tree(*many))

    code_context.build(
        gh,
        title="Subsonic playback fails",
        body="Playback stops immediately on every track.",
        diagnostics=_diagnostics(message="playback failure"),
        provider_labels={"subsonic"},
        version="2.9.7",
    )

    fetched = [path for path in gh.raw_reads if path.startswith("music_assistant/")]
    assert len(set(fetched)) <= code_context._MAX_PROVIDER_FILES


def test_the_fetch_budget_is_per_provider_for_each_reported_provider():
    """Two reported providers means two directories, and two budgets."""
    tree = _tree(
        *(
            f"music_assistant/providers/{domain}/mod{index:02d}.py"
            for domain in ("opensubsonic", "spotify")
            for index in range(30)
        )
    )
    gh = FakeGH(tree=tree)

    code_context.build(
        gh,
        title="Subsonic and Spotify playback both fail",
        body="Playback stops immediately on every track from either source.",
        diagnostics=_diagnostics(message="playback failure"),
        provider_labels={"subsonic", "spotify"},
        version="2.9.7",
    )

    fetched = {path for path in gh.raw_reads if path.startswith("music_assistant/")}
    assert len(fetched) <= code_context._MAX_PROVIDER_FILES * 2
    for domain in ("opensubsonic", "spotify"):
        in_domain = [p for p in fetched if f"/{domain}/" in p]
        assert 0 < len(in_domain) <= code_context._MAX_PROVIDER_FILES
