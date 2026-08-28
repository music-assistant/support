"""Tests for bounded official server-code evidence retrieval."""

import re

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


def test_excerpt_breaks_a_score_tie_toward_the_top_of_the_file():
    """Among lines that score equally, the earliest is the one quoted."""
    lines = ["filler"] * 400
    lines[10] = "def set_shuffle(queue_id, shuffle_enabled):"
    for index in range(300, 340):
        lines[index] = "queue.shuffle_enabled = shuffle_enabled"
    terms = {"shuffle", "enabled"}

    _, excerpt = code_context._excerpt("\n".join(lines), terms)

    shown = {int(n) for n in re.findall(r"^L(\d+): ", excerpt, re.M)}
    assert 11 in shown, f"the definition was never quoted: {sorted(shown)[:6]}"


def test_excerpt_spends_its_budget_on_more_places_not_more_context():
    """A file's relevant code is rarely all in one spot, so only the best
    window keeps its full surroundings and the rest are tightened.
    """
    lines = ["a fairly long line of filler that eats into the budget"] * 900
    relevant = tuple(range(20, 900, 60))
    for index in relevant:
        lines[index] = "shuffle_enabled matters on this particular line here"
    terms = {"shuffle", "enabled", "matters"}

    _, excerpt = code_context._excerpt("\n".join(lines), terms, max_chars=1000)

    shown = {int(n) for n in re.findall(r"^L(\d+): ", excerpt, re.M)}
    reached = sum(1 for index in relevant if index + 1 in shown)
    assert len(excerpt) <= 1000
    assert reached >= 4, f"only reached {reached} of {len(relevant)} locations"


def test_excerpt_never_quotes_the_same_line_twice():
    """Windows that overlap would repeat lines and split one contiguous region
    into what reads as several separate places in the file."""
    lines = ["filler"] * 400
    for index in range(100, 140):
        lines[index] = "queue.shuffle_enabled = shuffle_enabled"

    _, excerpt = code_context._excerpt("\n".join(lines), {"shuffle", "enabled"})

    quoted = [int(n) for n in re.findall(r"^L(\d+): ", excerpt, re.M)]
    assert len(quoted) == len(set(quoted)), f"repeated lines: {sorted(quoted)}"


def test_build_reaches_several_files_when_each_one_fills_its_share():
    """The per-file budget is a share of the total, so a long first file cannot
    swallow the whole block and starve the ones behind it."""
    paths = [f"music_assistant/providers/opensubsonic/mod{n}.py" for n in range(6)]
    body = "\n".join(
        f"def handler_{n}(): return 'playback stalled on subsonic'" for n in range(60)
    )
    gh = FakeGH(
        tree=_tree(*paths),
        raw_files={path: body for path in paths},
    )

    evidence = code_context.build(
        gh,
        title="Subsonic playback stalled",
        body="Playback stalled on every track.",
        diagnostics=_diagnostics(message="playback stalled"),
        provider_labels={"subsonic"},
        version="2.9.7",
    )

    assert evidence.count("SOURCE: ") >= 4
    assert len(evidence) <= config.MAX_CODE_CONTEXT_CHARS


def _traced(monkeypatch, path, *, line, symbol, offset):
    monkeypatch.setattr(
        code_context.code_trace, "load",
        lambda: [{"path": path, "line": line, "symbol": symbol, "offset": offset}],
    )


def _shifted_source(pad):
    """The same function, moved down the file by `pad` lines.

    The interesting line sits well below the `def`, so a window anchored on the
    definition cannot reach it by accident.
    """
    return "\n".join(
        ["# filler"] * pad
        + ["def apply_shuffle(queue):"]
        + [f"    step_{n}()" for n in range(12)]
        + ["    queue.shuffle_enabled = True"]
    )


def test_a_traced_location_is_found_after_the_file_has_shifted(monkeypatch):
    """The trace searches one tree and the reader fetches another. Line numbers
    do not survive that; the enclosing symbol does."""
    path = "music_assistant/controllers/player_queues/controller.py"
    gh = FakeGH(raw_files={path: _shifted_source(400)})
    # Traced against a tree where the function sat at line 10; the line of
    # interest was 13 lines further down.
    _traced(monkeypatch, path, line=23, symbol="apply_shuffle", offset=13)

    evidence = code_context.build(
        gh,
        title="Shuffle does nothing until playback starts",
        body="Enabling shuffle before play has no effect.",
        diagnostics=_diagnostics(message="shuffle not applied"),
        provider_labels=set(),
        version="2.9.7",
    )

    assert "queue.shuffle_enabled = True" in evidence
    assert "L414:" in evidence, "the offset was not applied to the symbol"
    assert "L401:" not in evidence, "quoted the definition instead of the line"


def test_a_traced_location_falls_back_when_the_symbol_is_gone(monkeypatch):
    """A renamed or deleted function must not cost more than the anchor."""
    path = "music_assistant/controllers/player_queues/controller.py"
    gh = FakeGH(raw_files={path: _shifted_source(20)})
    _traced(monkeypatch, path, line=5, symbol="renamed_since", offset=0)

    evidence = code_context.build(
        gh,
        title="Shuffle does nothing until playback starts",
        body="Enabling shuffle before play has no effect.",
        diagnostics=_diagnostics(message="shuffle not applied"),
        provider_labels=set(),
        version="2.9.7",
    )

    # The stale line points at filler, so quoting it would find nothing. Only
    # ordinary excerpting can reach the line that matters.
    assert "shuffle_enabled" in evidence, "fell through to nothing at all"
    assert "L5:" not in evidence, "quoted the stale line instead of excerpting"


def test_a_traced_location_with_no_symbol_uses_the_line(monkeypatch):
    """Module-level code has no definition to anchor to."""
    path = "music_assistant/constants.py"
    body = "\n".join(f"SETTING_{n} = {n}" for n in range(40))
    gh = FakeGH(raw_files={path: body})
    _traced(monkeypatch, path, line=12, symbol="", offset=0)

    evidence = code_context.build(
        gh,
        title="Setting has the wrong default",
        body="SETTING_11 defaults incorrectly for shuffle.",
        diagnostics=_diagnostics(message="wrong default"),
        provider_labels=set(),
        version="2.9.7",
    )

    assert "L12:" in evidence


def test_a_traced_symbol_that_is_not_unique_is_not_guessed_at():
    """`stop`, `setup` and `__init__` recur several times in a real module;
    picking the first is how the wrong function gets quoted as evidence."""
    body = "\n".join(
        [
            "class First:",
            "    def stop(self):",
            "        self.playback_halted = True",
            "",
            "class Second:",
            "    def stop(self):",
            "        self.shuffle_enabled = False",
        ]
    )
    # Recorded against the *second* `stop`, so resolving by first match would
    # quote the wrong class under real-looking line numbers.
    _, excerpt = code_context._traced_excerpt(
        body, {"shuffle", "enabled"},
        {"path": "player.py", "line": 7, "symbol": "stop", "offset": 1},
    )

    # Ordinary excerpting picks the line the vocabulary points at, rather than
    # whichever `stop` happened to come first.
    assert "shuffle_enabled" in excerpt
    assert "playback_halted" not in excerpt


def test_an_offset_past_the_end_of_the_file_does_not_quote_nothing():
    """A function shorter in the reporter's version must not walk off it."""
    body = "def handler():\n    queue.shuffle_enabled = True\n"
    _, excerpt = code_context._traced_excerpt(
        body, {"shuffle", "enabled"},
        {"path": "x.py", "line": 90, "symbol": "handler", "offset": 400},
    )

    assert excerpt, "overshoot produced no evidence at all"
    assert "shuffle_enabled" in excerpt


def test_a_traced_window_is_scored_on_the_same_scale_as_any_other():
    """`build` ranks every candidate together and keeps five, so a traced
    snippet scored differently would be dropped before it is read."""
    body = "\n".join(
        ["def handler(queue):"]
        + [f"    queue.shuffle_enabled = {n}" for n in range(20)]
    )
    terms = {"shuffle", "enabled", "queue", "handler"}
    plain, _ = code_context._excerpt(body, terms)
    traced, _ = code_context._traced_excerpt(
        body, terms, {"path": "x.py", "line": 5, "symbol": "handler", "offset": 4}
    )

    assert traced > plain / 2, f"traced {traced} against untraced {plain}"
