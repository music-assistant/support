"""One place that runs the GitHub Copilot CLI.

The chat backend is a command rather than an endpoint, so it is reached as a
subprocess. Every rule about how that subprocess is launched is a security rule,
and they live here so a second caller cannot quietly disagree with the first:

* the prompt goes in on **stdin, never argv** — it carries issue text written by
  anyone, and argv is readable from the process table by every other step in the
  job;
* the token is passed **explicitly**, because the CLI will otherwise find its
  own credentials, and a run that silently authenticates as something else is
  worse than one that fails;
* every failure returns ``None`` with the reason printed, naming the caller, so
  a broken backend is distinguishable from a disabled one.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from . import config

# The CLI is given a constructed environment. Its input is issue text written by
# anyone, and the job around it holds an app token with `issues: write` in
# `GITHUB_TOKEN`; only what the CLI needs to start is copied through.
_ENV_PASSTHROUGH = ("PATH",)


def run(prompt: str, *, what: str) -> str | None:
    """Assistant text for ``prompt``, or ``None`` with the reason logged.

    ``what`` names the caller in that message, so a skipped step says which one.
    """
    args = ["copilot", "-s", "--no-ask-user", "--disable-builtin-mcps"]
    try:
        with tempfile.TemporaryDirectory(prefix="copilot-home-") as home:
            completed = subprocess.run(
                args,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=config.AI_CLI_TIMEOUT,
                env=_environment(home),
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


def _environment(home: str) -> dict[str, str]:
    """The complete environment for a CLI run, built from nothing.

    ``HOME`` points at a scratch directory. With ``HOME`` unset the CLI resolves
    the real one from the password database and reads the credentials and
    configuration stored there.
    """
    env = {name: os.environ[name] for name in _ENV_PASSTHROUGH if name in os.environ}
    env["HOME"] = home
    env["COPILOT_GITHUB_TOKEN"] = config.AI_CLI_TOKEN
    return env
