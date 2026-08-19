"""One place that runs the GitHub Copilot CLI.

The CLI replaced GitHub Models as the chat backend when Models was retired, so
it is reached as a subprocess rather than an endpoint. Every rule about how that
subprocess is launched is a security rule, and they live here so a second caller
cannot quietly disagree with the first:

* the prompt goes in on **stdin, never argv** — it carries issue text written by
  anyone, and argv is readable from the process table by every other step in the
  job;
* the token is passed **explicitly**, because the CLI will otherwise find its
  own credentials, and a run that silently authenticates as something else is
  worse than one that fails;
* every failure returns ``None`` with the reason printed, naming the caller. A
  silent or mislabelled failure here is what once hid a dead provider behind a
  green build for sixteen days.
"""

from __future__ import annotations

import os
import subprocess

from . import config


def run(prompt: str, *, what: str) -> str | None:
    """Assistant text for ``prompt``, or ``None`` with the reason logged.

    ``what`` names the caller in that message, so a skipped step says which one.
    """
    try:
        completed = subprocess.run(
            ["copilot", "-s", "--no-ask-user"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=config.AI_CLI_TIMEOUT,
            env={**os.environ, "COPILOT_GITHUB_TOKEN": config.AI_CLI_TOKEN},
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{what} skipped: {exc}")
        return None
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:200]
        print(f"{what} skipped: copilot exited {completed.returncode}: {detail}")
        return None
    return completed.stdout
