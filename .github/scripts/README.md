# Music Assistant issue triage bot (experimental)

Autonomous, AI-assisted triage for issues in `music-assistant/support`.

The bot reads the **diagnostics file** that reporters attach (produced by
_Settings → Download diagnostics_ in Music Assistant), or falls back to scanning
an attached **raw log file** (for older versions without the diagnostics
feature), posts a single sticky summary comment, applies setup/provider labels,
involves community provider maintainers, manages the issue's response state, and
can optionally hand a high-confidence bug to the **Copilot coding agent** on
`music-assistant/server` to draft a fix PR.

> ⚠️ **Experimental & dry-run by default.** With `TRIAGE_DRY_RUN` unset or
> `true`, the bot makes **no changes** — it only writes what it _would_ do to
> the Actions job summary. Set the repo variable `TRIAGE_DRY_RUN=false` to go
> live.

## How it works

Thin workflows call a small, testable Python package (`ma_triage`). All issue
content is treated as **untrusted** and is passed to the script via `env:` —
never interpolated into a shell command.

```
.github/
├── workflows/
│   ├── triage.yml            # issues opened/edited/reopened + new comments
│   ├── triage_scheduled.yml  # daily reminder / auto-close sweep
│   └── copilot_dispatch.yml  # hand a bug to the Copilot coding agent
└── scripts/
    ├── ma_triage/            # the bot (see module docstrings)
    ├── requirements.txt      # just `requests`
    └── tests/                # offline pytest suite + fixtures
```

### Issue forms
The bot branches on the issue form (detected from labels):
- **main bug report** (`triage`): full diagnostics/log analysis + summary;
- **frontend bug** (`triage`, `frontend`): checks a screenshot/recording is
  attached and required fields are filled — stays silent when the report is
  complete;
- **translation** (`triage`, `translation`): skipped entirely.

### Tier 0 — deterministic (always on)
From the diagnostics file the bot derives, with no AI:
- **version check** vs the latest server release (outdated / pre-release);
- **safe mode** banner;
- **providers in error** (with sanitized error text);
- **top exception fingerprints** by count;
- **provider/setup labels** — from the diagnostics census *and* provider names
  mentioned in the form text (only labels that already exist are applied);
- **community maintainer** ping (from each provider's `codeowners`, skipping the
  core `@music-assistant` team; never triggered by heuristic log parsing);
- low-disk and other resource hints.

If only a **raw log file** is attached (older Music Assistant versions), the bot
redacts it first — stripping tokens, home directories, emails, MAC addresses and
non-local IPs — then extracts the version banner, safe-mode, provider setup
errors and exception fingerprints from the redacted text. Only derived facts and
redacted snippets are ever echoed. Controlled by `TRIAGE_SCAN_LOGS` (default on).

If no usable attachment is present, or required template sections are empty, the
bot posts a friendly request explaining how to download the diagnostics report.

### Tier 1 — GitHub Models (optional)
When `TRIAGE_AI_ENABLED=true`, a bounded, sanitized summary is sent to the
GitHub Models API for a short, strictly-typed assessment (category, confidence,
likely cause, possibly-fixed-in version). Any failure degrades gracefully to the
Tier-0 result. Uses the default `GITHUB_TOKEN` with `models: read`.

### Tier 2 — Copilot coding-agent dispatch (optional, guarded)
A maintainer applies the `triage/dispatch-copilot` label (or runs the dispatch
workflow manually) to hand the bug to the Copilot coding agent on the server
repo. See **Copilot dispatch token** below.

## Response-state lifecycle

| Trigger | Effect |
|---|---|
| issue opened, info/diagnostics missing | request info; `waiting-for-user` |
| issue opened, valid diagnostics | analyse + label; `needs-attention` |
| reporter comments | `needs-attention`; clears `waiting-for-user` + reminders |
| maintainer comments | `waiting-for-user`; clears `needs-attention` |
| `waiting-for-user` ≥ 3 days | gentle reminder (`triage/reminded-1`) |
| `waiting-for-user` ≥ 7 days | close warning (`triage/reminded-2`) |
| ≥ 14 days inactivity | auto-close politely (reopen invite) |

Exempt from reminders/close: `bug`, `enhancement`, `pinned`,
`Fix to be Confirmed`, `triage/hold`. Closed threads are locked by the separate
`lock_threads.yml` workflow.

Maintainer override labels: `triage/hold` (pause automation), `triage/skip`
(never triage), `triage/dispatch-copilot` (hand to the coding agent).

## Configuration

### Repo variables (Settings → Secrets and variables → Actions → Variables)
| Variable | Default | Purpose |
|---|---|---|
| `TRIAGE_DRY_RUN` | `true` | Kill switch. `false` to make real changes. |
| `TRIAGE_AI_ENABLED` | `false` | Enable Tier-1 GitHub Models assessment. |
| `TRIAGE_SCAN_LOGS` | `true` | Scan an attached raw log (redacted) when no diagnostics report is present. |
| `TRIAGE_AI_MODEL` | `openai/gpt-4o-mini` | Model id for Tier 1. |
| `TRIAGE_COPILOT_AUTO` | `false` | Allow auto-recommending Tier-2 dispatch. |
| `TRIAGE_COPILOT_AUTO_DAILY_CAP` | `3` | Max auto dispatches/day. |
| `TRIAGE_COPILOT_AUTO_MIN_CONFIDENCE` | `0.75` | Min AI confidence to auto-dispatch. |

### Repo secret
| Secret | Needed for | Notes |
|---|---|---|
| `COPILOT_DISPATCH_TOKEN` | Tier 2 only | Must be a **user-to-server** token. |

### Copilot dispatch token
The coding-agent API only accepts a **user-to-server** token — the default
Actions `GITHUB_TOKEN` and GitHub App **installation** tokens do **not** work.
Provide one of:
1. **Machine-user fine-grained PAT** (simplest) on a bot account that has a
   Copilot seat and write access to `music-assistant/server`. Scopes:
   metadata:read, actions/contents/issues/pull-requests:read+write.
2. **`musicassistant-machine` App user-to-server token** via the device flow
   (enable Device Flow; authorize once as a Copilot-seated user). Disable token
   expiration for a long-lived `ghu_` token, or wire up refresh rotation.

The runtime verifies the agent is actually available (`suggestedActors`) before
dispatching, and skips cleanly otherwise.

## Security model

- Triggers are `issues`, `issue_comment` and `schedule` only — **no
  `pull_request_target`**.
- Issue content flows through `env:` → `os.environ`; it is never placed in a
  shell command line.
- Attachment downloads are **host-allowlisted** (`user-attachments` / repo
  `files`) and **byte-capped** while streaming; JSON is parsed with size/depth
  guards; nothing from a file is ever executed.
- Everything echoed back from a diagnostics file is escaped: `@mentions` and
  `#refs` are neutralised, HTML/markers are escaped, code spans/fences can't be
  broken out of, and strings are length-capped.
- Least-privilege permissions per workflow; one concurrent run per issue.

## Local development / testing

```bash
cd .github/scripts
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q            # fully offline; uses fixtures under tests/fixtures/
```

Run a subcommand locally in dry-run against a real issue (read-only):

```bash
export GITHUB_TOKEN=... REPOSITORY=music-assistant/support TRIAGE_DRY_RUN=true
export ISSUE_NUMBER=123
ISSUE_TITLE="$(gh issue view 123 --json title -q .title)" \
ISSUE_BODY="$(gh issue view 123 --json body -q .body)" \
python -m ma_triage triage
```

## Rollout

1. Land with `TRIAGE_DRY_RUN=true`; review job summaries on real issues.
2. Set `TRIAGE_DRY_RUN=false` to enable Tier-0/1 actions.
3. Provision `COPILOT_DISPATCH_TOKEN`; try Tier 2 via the dispatch workflow, then
   via the `triage/dispatch-copilot` label.
4. Optionally enable `TRIAGE_COPILOT_AUTO` with a low daily cap.

> Note: the per-form required-section lists in `ma_triage/template.py` and the
> provider→label maps in `ma_triage/config.py` (`PROVIDER_LABELS` and the free-
> text `PROVIDER_TEXT_ALIASES`) should be kept in sync with the issue forms and
> the repo's labels as they evolve.
