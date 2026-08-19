"""Tests for the one place that launches the Copilot CLI.

Each of these pins a security rule rather than a convenience, so they assert the
launch contract — argv, stdin, environment — not just the return value.
"""

import os

from ma_triage import config, copilot


def test_run_sends_the_prompt_on_stdin_not_argv(monkeypatch):
    """Issue text is written by anyone, and argv is readable from the process
    table by every other step in the job."""
    monkeypatch.setattr(config, "AI_CLI_TOKEN", "tok")
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["input"] = kwargs.get("input")
        seen["env"] = kwargs.get("env")

        class R:
            returncode = 0
            stdout = "hello"
            stderr = ""

        return R()

    monkeypatch.setattr(copilot.subprocess, "run", fake_run)

    assert copilot.run("ISSUE BODY: something", what="X") == "hello"
    assert seen["args"] == [
        "copilot", "-s", "--no-ask-user", "--disable-builtin-mcps",
    ]
    assert not any("ISSUE BODY" in arg for arg in seen["args"])
    assert "ISSUE BODY" in seen["input"]
    # Passed explicitly: the CLI finds its own credentials otherwise, and
    # authenticating as something else silently is worse than failing.
    assert seen["env"]["COPILOT_GITHUB_TOKEN"] == "tok"


def test_run_hands_the_cli_a_built_environment_not_the_job_s(monkeypatch):
    """The job's own environment holds tokens this process must not reach."""
    monkeypatch.setenv("GITHUB_TOKEN", "app-token-with-issues-write")
    monkeypatch.setenv("GH_MODELS_TOKEN", "another-secret")
    monkeypatch.setattr(config, "AI_CLI_TOKEN", "tok")
    seen = {}

    def fake_run(args, **kwargs):
        seen["env"] = kwargs.get("env")

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(copilot.subprocess, "run", fake_run)
    copilot.run("prompt", what="X")

    assert "GITHUB_TOKEN" not in seen["env"]
    assert "GH_MODELS_TOKEN" not in seen["env"]
    assert set(seen["env"]) <= {"PATH", "HOME", "COPILOT_GITHUB_TOKEN"}


def test_run_points_home_at_a_scratch_directory(monkeypatch):
    """Set, never merely omitted: with no HOME the CLI resolves the real one
    from the password database and reads the credentials stored there."""
    monkeypatch.setattr(config, "AI_CLI_TOKEN", "tok")
    seen = {}

    def fake_run(args, **kwargs):
        seen["home"] = kwargs["env"]["HOME"]
        seen["exists"] = os.path.isdir(seen["home"])

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(copilot.subprocess, "run", fake_run)
    copilot.run("prompt", what="X")

    assert seen["exists"]
    assert seen["home"] != os.path.expanduser("~")
    # Cleaned up once the run is over.
    assert not os.path.isdir(seen["home"])


def test_run_returns_none_and_names_the_caller_on_a_non_zero_exit(
    monkeypatch, capsys
):
    class R:
        returncode = 1
        stdout = ""
        stderr = "Access denied by policy settings"

    monkeypatch.setattr(copilot.subprocess, "run", lambda *a, **k: R())

    assert copilot.run("prompt", what="Doc-answer judge") is None
    out = capsys.readouterr().out
    assert "Access denied by policy settings" in out
    assert "Doc-answer judge" in out


def test_run_returns_none_and_names_the_caller_when_the_cli_is_missing(
    monkeypatch, capsys
):
    """An absent binary must skip the step, never break triage."""

    def boom(*args, **kwargs):
        raise OSError("No such file or directory: 'copilot'")

    monkeypatch.setattr(copilot.subprocess, "run", boom)

    assert copilot.run("prompt", what="AI assessment") is None
    out = capsys.readouterr().out
    assert "AI assessment" in out
    assert "No such file or directory" in out
