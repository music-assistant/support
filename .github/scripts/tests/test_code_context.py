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


def test_build_retrieves_provider_and_packaging_evidence():
    gh = FakeGH(
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
