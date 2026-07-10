"""Command-line entry point for the Music Assistant triage bot.

Thin orchestration only — all logic lives in the sibling modules. Workflows call
one of the subcommands and pass everything via environment variables (never via
shell interpolation of untrusted issue content):

    python -m ma_triage triage     # analyse an opened/edited issue
    python -m ma_triage respond     # react to a new issue comment
    python -m ma_triage sweep       # scheduled reminder / auto-close pass
    python -m ma_triage dispatch    # hand a bug off to the Copilot coding agent

Required env: ``GITHUB_TOKEN``. Issue subcommands also read ``ISSUE_NUMBER``
(and, for triage, ``ISSUE_TITLE`` / ``ISSUE_BODY``). Feature flags come from the
``TRIAGE_*`` repo variables (see :mod:`ma_triage.config`).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any

from . import ai, analyze, comment, config, copilot, lifecycle, template
from .attachments import download_capped, find_diagnostics_url
from .diagnostics import try_parse
from .gh import GitHubClient, log, summary
from .models import TriageResult
from .providers import filter_existing_labels, resolve_maintainers


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Shared analysis pipeline (no mutations)
# --------------------------------------------------------------------------- #
def build_result(
    gh: GitHubClient, title: str, body: str, *, token: str
) -> TriageResult:
    """Run the full read-only analysis pipeline and return a TriageResult."""
    result = TriageResult()
    result.missing_sections = template.missing_sections(body)
    result.log_wall_detected = template.detect_log_wall(body)

    url = find_diagnostics_url(body)
    if url:
        raw = download_capped(url)
        if raw is None:
            result.diagnostics_invalid = True
        else:
            diag = try_parse(raw)
            if diag is None:
                result.diagnostics_invalid = True
            else:
                result.has_diagnostics = True
                result.diagnostics = diag

    if result.is_actionable and result.diagnostics is not None:
        diag = result.diagnostics
        findings, suggested = analyze.analyze(diag, gh)
        result.findings = findings
        result.labels_to_add |= suggested

        for provider in diag.providers_in_error:
            for handle in resolve_maintainers(gh, provider.domain):
                result.maintainers_to_ping.add(handle)

        ai_result = ai.assess(
            diag,
            title,
            body,
            token=token,
            candidate_labels=sorted(suggested),
        )
        if ai_result is not None:
            result.ai = ai_result
            result.labels_to_add.update(ai_result.suggested_labels)

    return result


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
def _resolve_labels(gh: GitHubClient, result: TriageResult) -> list[str]:
    """Intersect suggested labels with labels that actually exist in the repo."""
    existing = gh.list_labels()
    keep = filter_existing_labels(result.labels_to_add, existing)

    # Response-state labels (only apply if present in the repo).
    if result.is_actionable:
        state_label = config.LABEL_NEEDS_ATTENTION
    else:
        state_label = config.LABEL_WAITING_FOR_USER
        if config.LABEL_NEEDS_DIAGNOSTICS in existing:
            keep.add(config.LABEL_NEEDS_DIAGNOSTICS)
    if state_label in existing:
        keep.add(state_label)
    return sorted(keep)


def apply_triage(
    gh: GitHubClient,
    number: int,
    issue: dict[str, Any],
    result: TriageResult,
    prior_state: dict[str, Any],
) -> None:
    """Post the sticky comment and apply labels for a triage pass."""
    labels = _resolve_labels(gh, result)
    if labels:
        gh.add_labels(number, labels)

    state = {
        "v": 1,
        "last_run": _now_iso(),
        "has_diagnostics": result.has_diagnostics,
        "invalid": result.diagnostics_invalid,
        "ai": result.ai is not None,
    }
    if result.diagnostics is not None:
        state["version"] = result.diagnostics.system.version
    if "dispatch" in prior_state:  # preserve any earlier Copilot dispatch record
        state["dispatch"] = prior_state["dispatch"]

    body = comment.build_body(result)
    comment.upsert(gh, number, body, state)

    if config.COPILOT_AUTO and copilot.should_auto_dispatch(result):
        summary(
            f"#{number}: meets auto-dispatch criteria "
            f"(category=bug, confidence≥{config.COPILOT_AUTO_MIN_CONFIDENCE}). "
            "Apply the 'triage/dispatch-copilot' label (or run the dispatch "
            "workflow) to hand it to the Copilot coding agent."
        )


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #
def cmd_triage(gh: GitHubClient, token: str) -> int:
    number = int(_env("ISSUE_NUMBER"))
    title = _env("ISSUE_TITLE")
    body = _env("ISSUE_BODY")

    issue = gh.get_issue(number)
    labels = lifecycle.issue_labels(issue)
    if config.LABEL_HOLD in labels or config.LABEL_SKIP in labels:
        summary(f"#{number}: skipped (hold/skip label present).")
        return 0

    comments = gh.list_comments(number)
    prior_state = comment.parse_state(
        (comment.find_sticky(comments) or {}).get("body")
    )

    summary(f"## Triage of #{number}\n")
    result = build_result(gh, title, body, token=token)
    summary(
        f"- diagnostics: {'valid' if result.is_actionable else 'missing/invalid'}"
        f" · findings: {len(result.findings)} · ai: {result.ai is not None}"
    )
    apply_triage(gh, number, issue, result, prior_state)
    return 0


def cmd_respond(gh: GitHubClient) -> int:
    number = int(_env("ISSUE_NUMBER"))
    actor = _env("COMMENT_AUTHOR_LOGIN")
    association = _env("COMMENT_AUTHOR_ASSOCIATION", "NONE")
    user_type = _env("COMMENT_USER_TYPE")

    if user_type == "Bot" or actor.endswith("[bot]") or not actor:
        summary(f"#{number}: comment by bot/unknown; ignoring.")
        return 0

    issue = gh.get_issue(number)
    lifecycle.on_comment(
        gh, issue, actor_login=actor, author_association=association
    )
    return 0


def cmd_sweep(gh: GitHubClient) -> int:
    summary("## Scheduled triage sweep\n")
    lifecycle.sweep(gh)
    return 0


def cmd_dispatch(gh: GitHubClient, token: str) -> int:
    number = int(_env("ISSUE_NUMBER"))
    dispatch_token = os.environ.get("COPILOT_DISPATCH_TOKEN")

    issue = gh.get_issue(number)
    title = issue.get("title") or _env("ISSUE_TITLE")
    body = issue.get("body") or _env("ISSUE_BODY")

    summary(f"## Copilot dispatch for #{number}\n")
    result = build_result(gh, title, body, token=token)
    if not result.is_actionable:
        summary(f"#{number}: no valid diagnostics; not dispatching.")
        return 0
    if not copilot.within_daily_cap(gh):
        summary(f"#{number}: daily Copilot dispatch cap reached; skipping.")
        return 0

    outcome = copilot.dispatch(gh, issue, result, token=dispatch_token)
    summary(f"#{number}: dispatch → {outcome.reason}")

    # Record the outcome in the sticky comment's state for traceability.
    comments = gh.list_comments(number)
    sticky = comment.find_sticky(comments)
    state = comment.parse_state(sticky.get("body") if sticky else None)
    state["dispatch"] = {
        "at": _now_iso(),
        "dispatched": outcome.dispatched,
        "reason": outcome.reason,
        "task_url": outcome.task_url,
        "pr_url": outcome.pr_url,
    }
    if sticky:
        body_only = (sticky["body"] or "").split(config.STATE_BEGIN)[0].rstrip()
        comment.upsert(gh, number, body_only, state, comments=comments)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        log("usage: python -m ma_triage {triage|respond|sweep|dispatch}")
        return 2
    command = argv[0]

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log("GITHUB_TOKEN is required")
        return 2
    repo = os.environ.get("REPOSITORY", config.SUPPORT_REPO)
    gh = GitHubClient(token, repo=repo)

    if config.DRY_RUN:
        summary("> 🟡 **Dry-run mode** — no changes will be made.\n")

    if command == "triage":
        return cmd_triage(gh, token)
    if command == "respond":
        return cmd_respond(gh)
    if command == "sweep":
        return cmd_sweep(gh)
    if command == "dispatch":
        return cmd_dispatch(gh, token)
    log(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
