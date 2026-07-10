"""Regression tests for env-driven config parsing.

GitHub Actions passes an unset ``${{ vars.X }}`` as an *empty string*, not an
absent variable. A plain ``int(os.environ.get(name, default))`` therefore sees
``""`` and raises ``ValueError`` at import time (which took the whole bot down).
These tests lock in that empty/blank env vars fall back to the defaults.
"""

import importlib

import pytest


def _reload_config(monkeypatch, **env):
    import ma_triage.config as config

    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def _restore_config():
    # Reload once after each test so later tests see the pristine module.
    yield
    import ma_triage.config as config

    importlib.reload(config)


def test_empty_env_vars_fall_back_to_defaults(monkeypatch):
    # Mimic the workflow passing every unset repo var as an empty string.
    config = _reload_config(
        monkeypatch,
        TRIAGE_EMBED_DIM="",
        TRIAGE_EMBED_BATCH="",
        TRIAGE_ANSWER_HI="",
        TRIAGE_ANSWER_LO="",
        TRIAGE_RELATED_POSTS="",
        TRIAGE_INDEX_MAX_POSTS="",
        TRIAGE_EMBED_MODEL="",
        TRIAGE_ANSWER_MODEL="",
        TRIAGE_INDEX_BRANCH="",
        TRIAGE_DOCS_REPO="",
        TRIAGE_COPILOT_AUTO_DAILY_CAP="",
    )
    assert config.EMBED_DIM == 512
    assert config.EMBED_BATCH == 64
    assert config.ANSWER_HI == 0.75
    assert config.ANSWER_LO == 0.45
    assert config.RELATED_POSTS == 3
    assert config.INDEX_MAX_POSTS == 500
    assert config.COPILOT_AUTO_DAILY_CAP == 3
    assert config.EMBED_MODEL == "openai/text-embedding-3-small"
    assert config.ANSWER_MODEL == "openai/gpt-4o"
    assert config.INDEX_BRANCH == "triage-index"
    assert config.DOCS_REPO == "music-assistant/music-assistant.io"


def test_set_env_vars_are_honoured(monkeypatch):
    config = _reload_config(
        monkeypatch,
        TRIAGE_EMBED_DIM="256",
        TRIAGE_ANSWER_HI="0.9",
        TRIAGE_INDEX_BRANCH="custom-index",
        TRIAGE_EMBED_MODEL="openai/text-embedding-3-large",
    )
    assert config.EMBED_DIM == 256
    assert config.ANSWER_HI == 0.9
    assert config.INDEX_BRANCH == "custom-index"
    assert config.EMBED_MODEL == "openai/text-embedding-3-large"


def test_garbage_numeric_env_falls_back_not_crashes(monkeypatch):
    config = _reload_config(
        monkeypatch, TRIAGE_EMBED_DIM="not-a-number", TRIAGE_ANSWER_HI="  "
    )
    assert config.EMBED_DIM == 512
    assert config.ANSWER_HI == 0.75
