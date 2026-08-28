"""Tests for model-driven code tracing.

The model's answer is not deterministic, so what these pin is everything around
it: that tracing stays off until asked for, that only paths naming a real file
inside the checkout survive, and that a failure degrades to a logged skip.
"""

import json

from ma_triage import code_trace, config


SOURCE = "def handler():\n    value = 1\n    return value\n"


def _checkout(tmp_path, *paths):
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(SOURCE)
    return tmp_path


def _reply(*locations):
    return json.dumps({"locations": list(locations)})


def _at(path, line=2, symbol="handler"):
    return {"path": path, "line": line, "symbol": symbol}


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
    reply = _reply(
        _at("music_assistant/controllers/players.py"),
        _at("music_assistant/providers/sonos/player.py"),
    )
    seen = _enable(monkeypatch, checkout, reply)

    found = code_trace.trace(title="Players drop out", body="They disconnect.")
    assert [item["path"] for item in found] == [
        "music_assistant/controllers/players.py",
        "music_assistant/providers/sonos/player.py",
    ]
    # Line 2 sits one line below `def handler` on line 1.
    assert found[0]["symbol"] == "handler" and found[0]["offset"] == 1
    assert seen["cwd"] == str(checkout)


def test_only_tools_that_cannot_execute_another_binary_are_granted(
    monkeypatch, tmp_path
):
    """`--allow-tool` matches the binary name, not argv, so one exec primitive
    is a shell: `find -exec`, GNU `sed`'s `e`, and `rg --pre` each run anything."""
    seen = _enable(monkeypatch, _checkout(tmp_path, "a.py"), '{"locations": []}')
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
    reply = _reply(_at("../secret.txt"), _at("/etc/passwd"),
                   _at("music_assistant/real.py"))
    _enable(monkeypatch, checkout, reply)

    found = code_trace.trace(title="t", body="b")
    assert [item["path"] for item in found] == ["music_assistant/real.py"]
    assert "outside the checkout" in capsys.readouterr().err


def test_a_path_that_does_not_exist_is_refused(monkeypatch, tmp_path):
    checkout = _checkout(tmp_path, "music_assistant/real.py")
    _enable(monkeypatch, checkout, _reply(_at("music_assistant/invented.py")))
    assert code_trace.trace(title="t", body="b") == []


def test_prose_instead_of_json_is_a_logged_skip(monkeypatch, tmp_path, capsys):
    """The CLI has no `response_format`, so the shape is a request not a promise."""
    _enable(monkeypatch, _checkout(tmp_path, "a.py"), "I think it's the network.")
    assert code_trace.trace(title="t", body="b") == []
    assert "no usable locations" in capsys.readouterr().err


def test_a_cli_failure_degrades_to_no_paths(monkeypatch, tmp_path):
    _enable(monkeypatch, _checkout(tmp_path, "a.py"), None)
    assert code_trace.trace(title="t", body="b") == []


def test_the_report_is_capped_before_it_reaches_the_model(monkeypatch, tmp_path):
    seen = _enable(monkeypatch, _checkout(tmp_path, "a.py"), '{"locations": []}')
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


def _record(tmp_path, monkeypatch, payload):
    recorded = tmp_path / "traced.json"
    recorded.write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(recorded))


def test_load_reads_the_locations_the_trace_job_recorded(monkeypatch, tmp_path):
    _record(tmp_path, monkeypatch, [
        {"path": "music_assistant/helpers/util.py", "line": 40,
         "symbol": "parse_tag", "offset": 6}])
    assert code_trace.load() == [
        {"path": "music_assistant/helpers/util.py", "line": 40,
         "symbol": "parse_tag", "offset": 6}]


def test_load_refuses_a_path_that_could_steer_a_url(monkeypatch, tmp_path):
    """The artifact crosses a job boundary and each path becomes a fetch URL."""
    _record(tmp_path, monkeypatch, [
        {"path": "../../etc/passwd", "line": 1, "symbol": "", "offset": 0},
        {"path": "/etc/passwd", "line": 1, "symbol": "", "offset": 0},
        {"path": "music_assistant/a/../../b.py", "line": 1, "symbol": "", "offset": 0},
        {"path": "music_assistant/helpers/util.py", "line": 9,
         "symbol": "ok", "offset": 2},
    ])
    assert [item["path"] for item in code_trace.load()] == [
        "music_assistant/helpers/util.py"]


def test_load_refuses_a_malformed_anchor(monkeypatch, tmp_path):
    """A symbol becomes a regex-free lookup, and a line becomes an index."""
    _record(tmp_path, monkeypatch, [
        {"path": "a.py", "line": "nope", "symbol": "", "offset": 0},
        {"path": "b.py", "line": 3, "symbol": "not an identifier", "offset": 0},
        {"path": "c.py", "line": 0, "symbol": "", "offset": 0},
        {"path": "d.py", "line": 3, "symbol": "", "offset": -5},
        {"path": "e.py", "line": 3, "symbol": "fine", "offset": 1},
    ])
    assert [item["path"] for item in code_trace.load()] == ["e.py"]


def test_load_survives_a_corrupt_artifact(monkeypatch, tmp_path, capsys):
    _record(tmp_path, monkeypatch, "{not json")
    assert code_trace.load() == []
    assert "Traced locations ignored" in capsys.readouterr().err


def test_a_symbol_that_does_not_enclose_the_line_is_refused(monkeypatch, tmp_path):
    """The model must have opened the file, not guessed a plausible name."""
    checkout = _checkout(tmp_path, "music_assistant/real.py")
    _enable(monkeypatch, checkout,
            _reply(_at("music_assistant/real.py", line=2, symbol="somewhere_else")))
    assert code_trace.trace(title="t", body="b") == []


def test_a_line_past_the_end_of_the_file_is_refused(monkeypatch, tmp_path):
    checkout = _checkout(tmp_path, "music_assistant/real.py")
    _enable(monkeypatch, checkout,
            _reply(_at("music_assistant/real.py", line=9000, symbol="handler")))
    assert code_trace.trace(title="t", body="b") == []


# --------------------------------------------------------------------------- #
# The `trace` subcommand, which is the whole of the separate job.
# --------------------------------------------------------------------------- #
def _run_command(monkeypatch, tmp_path, *, body, enabled=True, traced=None):
    from ma_triage import __main__ as main

    destination = tmp_path / "traced-paths.json"
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(destination))
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", enabled)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(tmp_path))
    monkeypatch.setenv("ISSUE_TITLE", "Players drop out")
    monkeypatch.setenv("ISSUE_BODY", body)
    monkeypatch.setattr(
        main.code_trace, "trace", lambda **kwargs: list(traced or [])
    )
    code = main.cmd_trace()
    written = json.loads(destination.read_text()) if destination.exists() else None
    return code, written


def test_the_trace_command_needs_no_github_token(monkeypatch, tmp_path):
    """It reads a local checkout and writes a local file, nothing more — so the
    job that runs it is never handed a credential."""
    from ma_triage import __main__ as main

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(tmp_path / "out.json"))
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", False)
    assert main.main(["trace"]) == 0


def test_the_trace_command_records_what_it_found(monkeypatch, tmp_path):
    code, written = _run_command(
        monkeypatch,
        tmp_path,
        body="Logs attached https://github.com/user-attachments/files/1/diag.json",
        traced=["music_assistant/helpers/util.py"],
    )
    assert code == 0
    assert written == ["music_assistant/helpers/util.py"]


def test_the_trace_command_writes_an_empty_result_when_disabled(
    monkeypatch, tmp_path
):
    """`analyze` downloads this artifact; absent and empty must mean the same."""
    code, written = _run_command(
        monkeypatch,
        tmp_path,
        body="Logs attached https://github.com/user-attachments/files/1/diag.json",
        enabled=False,
        traced=["never/used.py"],
    )
    assert code == 0
    assert written == []


def test_the_trace_command_skips_a_report_with_no_diagnostics(monkeypatch, tmp_path):
    """Without diagnostics the report never reaches the assessment, so a traced
    path would have no consumer and the model call would be spent for nothing."""
    code, written = _run_command(
        monkeypatch,
        tmp_path,
        body="It just stopped working, no file attached.",
        traced=["music_assistant/helpers/util.py"],
    )
    assert code == 0
    assert written == []


def _run_with_capture(monkeypatch, tmp_path, *, title=""):
    """Run `cmd_trace` and report the title and body the tracer was handed."""
    from ma_triage import __main__ as main

    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(tmp_path / "out.json"))
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", True)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(tmp_path))
    if title:
        monkeypatch.setenv("ISSUE_TITLE", title)
    seen = {}

    def fake_trace(*, title, body):
        seen["title"] = title
        seen["body"] = body
        return []

    monkeypatch.setattr(main.code_trace, "trace", fake_trace)
    main.cmd_trace()
    return seen


def test_the_trace_command_reads_the_issue_the_workflow_fetched(
    monkeypatch, tmp_path
):
    """A manual dispatch carries no issue payload, so the environment is empty
    on exactly the path a maintainer uses to test."""
    from ma_triage import __main__ as main

    fetched = tmp_path / "issue.json"
    fetched.write_text(
        json.dumps(
            {
                "title": "Playback stops after ten minutes",
                "body": "Logs: https://github.com/user-attachments/files/1/diag.json",
            }
        )
    )
    destination = tmp_path / "traced-paths.json"
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(destination))
    monkeypatch.setattr(config, "CODE_TRACE_ISSUE_FILE", str(fetched))
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", True)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(tmp_path))
    monkeypatch.delenv("ISSUE_TITLE", raising=False)
    monkeypatch.delenv("ISSUE_BODY", raising=False)
    seen = {}

    def fake_trace(*, title, body):
        seen["title"] = title
        seen["body"] = body
        return ["music_assistant/helpers/util.py"]

    monkeypatch.setattr(main.code_trace, "trace", fake_trace)

    assert main.cmd_trace() == 0
    assert seen["title"] == "Playback stops after ten minutes"
    assert json.loads(destination.read_text()) == ["music_assistant/helpers/util.py"]


def test_the_event_payload_wins_over_the_fetched_copy(monkeypatch, tmp_path):
    """An issue event already carries the text; the fetch is for dispatch only."""
    from ma_triage import __main__ as main

    fetched = tmp_path / "issue.json"
    fetched.write_text(json.dumps({"title": "stale", "body": "stale"}))
    monkeypatch.setattr(config, "CODE_TRACE_ISSUE_FILE", str(fetched))
    monkeypatch.setenv("ISSUE_BODY", "https://github.com/user-attachments/files/1/d.json")
    seen = _run_with_capture(monkeypatch, tmp_path, title="from the event")

    assert seen["title"] == "from the event"
    assert "stale" not in seen["body"]


def test_an_unreadable_fetched_issue_reports_the_wiring_not_the_report(
    monkeypatch, tmp_path, capsys
):
    """This command cannot fail, so its log is the only place a broken wiring
    can show itself — and it must not read as a property of the report."""
    from ma_triage import __main__ as main

    broken = tmp_path / "issue.json"
    broken.write_text("{not json")
    destination = tmp_path / "traced-paths.json"
    monkeypatch.setattr(config, "CODE_TRACE_ISSUE_FILE", str(broken))
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(destination))
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", True)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(tmp_path))
    monkeypatch.delenv("ISSUE_TITLE", raising=False)
    monkeypatch.delenv("ISSUE_BODY", raising=False)

    assert main.cmd_trace() == 0
    err = capsys.readouterr().err
    assert "Could not read the fetched issue" in err
    assert "never reached this job" in err
    assert "No diagnostics attached" not in err
    assert json.loads(destination.read_text()) == []


def test_no_payload_and_no_fetched_copy_names_the_missing_wiring(
    monkeypatch, tmp_path, capsys
):
    """The configuration as shipped before the fetch step existed."""
    from ma_triage import __main__ as main

    destination = tmp_path / "traced-paths.json"
    monkeypatch.setattr(config, "CODE_TRACE_ISSUE_FILE", "")
    monkeypatch.setattr(config, "CODE_TRACE_PATHS_FILE", str(destination))
    monkeypatch.setattr(config, "CODE_TRACE_ENABLED", True)
    monkeypatch.setattr(config, "CODE_TRACE_CHECKOUT", str(tmp_path))
    monkeypatch.delenv("ISSUE_TITLE", raising=False)
    monkeypatch.delenv("ISSUE_BODY", raising=False)

    assert main.cmd_trace() == 0
    err = capsys.readouterr().err
    assert "TRIAGE_ISSUE_FILE" in err
    assert "No diagnostics attached" not in err
