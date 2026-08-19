"""Tests for model-driven code tracing.

The model's answer is not deterministic, so what these pin is everything around
it: that tracing stays off until asked for, that only paths naming a real file
inside the checkout survive, and that a failure degrades to a logged skip.
"""

import json

from ma_triage import code_trace, config


def _checkout(tmp_path, *paths):
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n")
    return tmp_path


def _enable(monkeypatch, checkout, reply):
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", True)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(checkout))
    seen = {}

    def fake_run(prompt, **kwargs):
        seen.update(kwargs)
        seen["prompt"] = prompt
        return reply

    monkeypatch.setattr(code_trace.copilot, "run", fake_run)
    return seen


def test_tracing_is_off_until_a_maintainer_turns_it_on(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", False)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(tmp_path))

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("the CLI was launched while tracing was disabled")

    monkeypatch.setattr(code_trace.copilot, "run", explode)
    assert code_trace.trace(title="t", body="b") == []


def test_tracing_needs_a_checkout_even_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", True)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", "")
    assert code_trace.trace(title="t", body="b") == []


def test_missing_checkout_directory_is_a_logged_skip(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", True)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(tmp_path / "absent"))
    assert code_trace.trace(title="t", body="b") == []
    assert "no checkout" in capsys.readouterr().err


def test_returns_the_ranked_paths_that_exist_in_the_checkout(monkeypatch, tmp_path):
    checkout = _checkout(
        tmp_path,
        "music_assistant/providers/sonos/player.py",
        "music_assistant/controllers/players.py",
    )
    reply = json.dumps(
        {
            "paths": [
                "music_assistant/controllers/players.py",
                "music_assistant/providers/sonos/player.py",
            ]
        }
    )
    seen = _enable(monkeypatch, checkout, reply)

    assert code_trace.trace(title="Players drop out", body="They disconnect.") == [
        "music_assistant/controllers/players.py",
        "music_assistant/providers/sonos/player.py",
    ]
    assert seen["cwd"] == str(checkout)


def test_only_tools_that_cannot_execute_another_binary_are_granted(
    monkeypatch, tmp_path
):
    """`--allow-tool` matches the binary name, not argv, so one exec primitive
    is a shell: `find -exec`, GNU `sed`'s `e`, and `rg --pre` each run anything."""
    seen = _enable(monkeypatch, _checkout(tmp_path, "a.py"), '{"paths": []}')
    code_trace.trace(title="t", body="b")

    granted = set(seen["tools"])
    assert granted == {
        "shell(grep)",
        "shell(cat)",
        "shell(ls)",
        "shell(head)",
        "shell(wc)",
    }
    for exec_capable in ("shell(find)", "shell(sed)", "shell(rg)", "shell(bash)"):
        assert exec_capable not in granted


def test_a_path_outside_the_checkout_is_refused(monkeypatch, tmp_path, capsys):
    """The model may point at a file; it may not reach out of the tree."""
    checkout = _checkout(tmp_path / "server", "music_assistant/real.py")
    (tmp_path / "secret.txt").write_text("token")
    reply = json.dumps(
        {
            "paths": [
                "../secret.txt",
                "/etc/passwd",
                "music_assistant/real.py",
            ]
        }
    )
    _enable(monkeypatch, checkout, reply)

    assert code_trace.trace(title="t", body="b") == ["music_assistant/real.py"]
    assert "outside the checkout" in capsys.readouterr().err


def test_a_path_that_does_not_exist_is_refused(monkeypatch, tmp_path):
    checkout = _checkout(tmp_path, "music_assistant/real.py")
    reply = json.dumps({"paths": ["music_assistant/invented.py"]})
    _enable(monkeypatch, checkout, reply)
    assert code_trace.trace(title="t", body="b") == []


def test_prose_instead_of_json_is_a_logged_skip(monkeypatch, tmp_path, capsys):
    """The CLI has no `response_format`, so the shape is a request not a promise."""
    _enable(monkeypatch, _checkout(tmp_path, "a.py"), "I think it's the network.")
    assert code_trace.trace(title="t", body="b") == []
    assert "no usable paths" in capsys.readouterr().err


def test_a_cli_failure_degrades_to_no_paths(monkeypatch, tmp_path):
    _enable(monkeypatch, _checkout(tmp_path, "a.py"), None)
    assert code_trace.trace(title="t", body="b") == []


def test_the_report_is_capped_before_it_reaches_the_model(monkeypatch, tmp_path):
    seen = _enable(monkeypatch, _checkout(tmp_path, "a.py"), '{"paths": []}')
    code_trace.trace(title="t", body="x" * 50_000)
    assert len(seen["prompt"]) < config.MAX_TRACE_INPUT_CHARS + 2_000


# --------------------------------------------------------------------------- #
# The consumer half: paths arrive as a build artifact from another job.
# --------------------------------------------------------------------------- #
def test_load_returns_nothing_when_no_file_was_configured(monkeypatch):
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", "")
    assert code_trace.load() == []


def test_load_returns_nothing_when_the_trace_job_left_no_file(monkeypatch, tmp_path):
    """The trace job is allowed to fail, time out, or not have run at all."""
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(tmp_path / "absent.json"))
    assert code_trace.load() == []


def test_load_reads_the_paths_the_trace_job_recorded(monkeypatch, tmp_path):
    recorded = tmp_path / "traced.json"
    recorded.write_text(json.dumps(["music_assistant/helpers/util.py"]))
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(recorded))
    assert code_trace.load() == ["music_assistant/helpers/util.py"]


def test_load_refuses_a_path_that_could_steer_a_url(monkeypatch, tmp_path):
    """The artifact crosses a job boundary and each path becomes a fetch URL."""
    recorded = tmp_path / "traced.json"
    recorded.write_text(
        json.dumps(
            [
                "../../etc/passwd",
                "/etc/passwd",
                "music_assistant/a/../../b.py",
                "music_assistant/helpers/util.py",
            ]
        )
    )
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(recorded))
    assert code_trace.load() == ["music_assistant/helpers/util.py"]


def test_load_survives_a_corrupt_artifact(monkeypatch, tmp_path, capsys):
    recorded = tmp_path / "traced.json"
    recorded.write_text("{not json")
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(recorded))
    assert code_trace.load() == []
    assert "Traced paths ignored" in capsys.readouterr().err
