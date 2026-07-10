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

from . import ai, analyze, comment, config, copilot, embeddings, lifecycle, logscan, rag, template
from .attachments import (
    download_capped,
    download_log_windowed,
    find_diagnostics_url,
    find_log_urls,
    has_media_attachment,
)
from .diagnostics import try_parse
from .gh import GitHubClient, log, summary
from .models import TriageResult
from .providers import (
    detect_provider_labels_from_text,
    filter_existing_labels,
    resolve_maintainers,
)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Shared analysis pipeline (no mutations)
# --------------------------------------------------------------------------- #
def build_result(
    gh: GitHubClient,
    title: str,
    body: str,
    *,
    token: str,
    labels: set[str] | list[str] | None = None,
    number: int = 0,
) -> TriageResult:
    """Run the full read-only analysis pipeline and return a TriageResult.

    ``labels`` are the issue's current labels, used to pick the form kind.
    ``number`` is the issue number (used only to exclude the post itself from
    related-post detection).
    """
    kind = template.form_kind(labels)
    if kind == "translation":
        # Translation contributions are not bug reports — never triage them.
        return TriageResult(form_kind="translation", skip=True)

    result = TriageResult(form_kind=kind)
    result.missing_sections = template.missing_sections(body, kind)
    result.log_wall_detected = template.detect_log_wall(body)
    result.reported_version = template.extract_version(body)
    result.has_media_attachment = has_media_attachment(body)

    if kind == "frontend":
        # UI bug: the required "attachment" is a screenshot/recording.
        result.missing_attachment = not result.has_media_attachment
        return result

    # --- main server bug form ------------------------------------------------
    result.install_method = template.extract_install_method(body)
    _load_diagnostics_or_log(gh, body, result)

    findings = list(result.findings)
    labels_to_add: set[str] = set(result.labels_to_add)
    maintainers: set[str] = set()

    # Provider labels from the free-text fields + title (census gone from form).
    labels_to_add |= detect_provider_labels_from_text(
        template.provider_scan_text(body, title)
    )

    install_finding = analyze.install_method_finding(result.install_method)
    if install_finding is not None:
        findings.append(install_finding)

    if result.is_actionable and result.diagnostics is not None:
        diag = result.diagnostics
        a_findings, a_labels = analyze.analyze(diag, gh)
        findings.extend(a_findings)
        labels_to_add |= a_labels

        # Log-sourced reports rarely carry a version banner; fall back to the
        # value the reporter typed into the form.
        if not diag.system.version and result.reported_version:
            v_findings, v_labels = analyze.version_findings(
                result.reported_version, gh
            )
            findings.extend(v_findings)
            labels_to_add |= v_labels

        # Only involve maintainers from a *real* diagnostics census — log parsing
        # of provider names is heuristic and must not ping people.
        if diag.source == "json":
            for provider in diag.providers_in_error:
                for handle in resolve_maintainers(gh, provider.domain):
                    maintainers.add(handle)

        ai_result = ai.assess(
            diag, title, body, token=token, candidate_labels=sorted(labels_to_add)
        )
        if ai_result is not None:
            result.ai = ai_result
            labels_to_add.update(ai_result.suggested_labels)
    elif result.reported_version:
        # No attachment we could parse — still nudge on an outdated version.
        v_findings, v_labels = analyze.version_findings(result.reported_version, gh)
        findings.extend(v_findings)
        labels_to_add |= v_labels

    findings.sort(key=lambda f: f.sort_key)
    result.findings = findings
    result.labels_to_add = labels_to_add
    result.maintainers_to_ping = maintainers

    # Phase 2 RAG layer (docs-grounded answer + related posts). Returns None when
    # disabled or on any failure, so Tier-0/Tier-1 output is unchanged.
    result.rag = rag.answer(gh, title=title, body=body, number=number, token=token)
    return result


def _load_diagnostics_or_log(
    gh: GitHubClient, body: str, result: TriageResult
) -> None:
    """Populate diagnostics from an attached JSON report, else a raw log."""
    url = find_diagnostics_url(body)
    if url:
        raw = download_capped(url)
        if raw is None:
            result.diagnostics_invalid = True
            return
        diag = try_parse(raw)
        if diag is None:
            result.diagnostics_invalid = True
        else:
            result.has_diagnostics = True
            result.diagnostics = diag
        return

    log_urls = find_log_urls(body)
    if config.SCAN_LOGS and log_urls:
        text = download_log_windowed(log_urls[0])
        if text:
            result.has_diagnostics = True
            result.diagnostics = logscan.scan_log(text)
        else:
            result.diagnostics_invalid = True
        return

    # Nothing usable attached.
    result.missing_attachment = True


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
def _resolve_labels(gh: GitHubClient, result: TriageResult) -> list[str]:
    """Intersect suggested labels with labels that actually exist in the repo."""
    existing = gh.list_labels()
    keep = filter_existing_labels(result.labels_to_add, existing)

    # Response-state labels (only apply if present in the repo). A pending user
    # action takes precedence over actionability: e.g. valid diagnostics but an
    # empty required "What happened?" still means we're waiting on the reporter.
    if result.needs_user_action:
        state_label = config.LABEL_WAITING_FOR_USER
        if (
            result.form_kind == "main"
            and not result.has_diagnostics
            and config.LABEL_NEEDS_DIAGNOSTICS in existing
        ):
            keep.add(config.LABEL_NEEDS_DIAGNOSTICS)
    elif result.is_actionable:
        state_label = config.LABEL_NEEDS_ATTENTION
    else:
        # Complete report with nothing outstanding (e.g. a filled-in frontend bug).
        state_label = config.LABEL_NEEDS_ATTENTION
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
    """Apply labels and (when there's something useful to say) the sticky comment."""
    labels = _resolve_labels(gh, result)
    if labels:
        gh.add_labels(number, labels)

    if result.should_comment or (result.rag is not None and result.rag.has_output):
        state = {
            "v": 1,
            "last_run": _now_iso(),
            "form": result.form_kind,
            "has_diagnostics": result.has_diagnostics,
            "invalid": result.diagnostics_invalid,
            "ai": result.ai is not None,
        }
        if result.diagnostics is not None:
            state["version"] = result.diagnostics.system.version
            state["source"] = result.diagnostics.source
        if result.rag is not None:
            state["rag"] = {
                "tier": result.rag.tier,
                "cited": [c.id for c in result.rag.cited_chunks],
                "related": [p.number for p in result.rag.related_posts],
                "suppressed": result.rag.suppressed,
            }
        if "dispatch" in prior_state:  # preserve any earlier Copilot dispatch record
            state["dispatch"] = prior_state["dispatch"]

        body = comment.build_body(result)
        comment.upsert(gh, number, body, state)
    else:
        summary(
            f"#{number}: nothing actionable to post (form={result.form_kind}); "
            "applied labels only."
        )

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

    summary(f"## Triage of #{number}\n")
    result = build_result(gh, title, body, token=token, labels=labels, number=number)
    if result.skip:
        summary(f"#{number}: skipped ({result.form_kind} form — not triaged).")
        return 0

    comments = gh.list_comments(number)
    prior_state = comment.parse_state(
        (comment.find_sticky(comments) or {}).get("body")
    )

    summary(
        f"- form: {result.form_kind}"
        f" · diagnostics: {_diag_status(result)}"
        f" · findings: {len(result.findings)} · ai: {result.ai is not None}"
        f" · comment: {result.should_comment}"
    )
    apply_triage(gh, number, issue, result, prior_state)
    return 0


def _diag_status(result: TriageResult) -> str:
    if result.is_actionable and result.diagnostics is not None:
        return f"valid ({result.diagnostics.source})"
    if result.diagnostics_invalid:
        return "invalid"
    if result.form_kind == "frontend":
        return "n/a (frontend)"
    return "missing"


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
    labels = lifecycle.issue_labels(issue)

    summary(f"## Copilot dispatch for #{number}\n")
    result = build_result(gh, title, body, token=token, labels=labels, number=number)
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


# --------------------------------------------------------------------------- #
# RAG index build (Phase 2)
# --------------------------------------------------------------------------- #
def _build_docs_index(gh: GitHubClient, token: str) -> None:
    prev = embeddings.load_index(gh, config.DOCS_INDEX_PATH)
    index, changed = embeddings.build_docs_index(gh, token=token, previous=prev)
    if index is None:
        summary("- docs: build skipped (embeddings unavailable / rate limited)")
        return
    count = len(index.get("chunks", []))
    if not changed:
        summary(f"- docs: unchanged ({count} chunks); no commit")
        return
    embeddings.save_index(
        gh, config.DOCS_INDEX_PATH, index, message=f"Update docs index ({count} chunks)"
    )
    summary(f"- docs: {count} chunks indexed")


def _collect_posts(gh: GitHubClient) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for issue in gh.list_recent_issues(limit=config.INDEX_MAX_POSTS):
        posts.append(
            {
                "kind": "issue",
                "number": issue.get("number"),
                "title": issue.get("title") or "",
                "body": issue.get("body") or "",
                "url": issue.get("html_url") or "",
                "state": issue.get("state"),
                "updated_at": issue.get("updated_at"),
            }
        )
    for disc in gh.list_discussions(limit=config.INDEX_MAX_POSTS):
        category = ((disc.get("category") or {}).get("name") or "").lower()
        if category in config.DISCUSSION_EXCLUDE_CATEGORIES:
            # e.g. translation-category discussions: not useful as related posts.
            continue
        posts.append(
            {
                "kind": "discussion",
                "number": disc.get("number"),
                "title": disc.get("title") or "",
                "body": disc.get("body") or "",
                "url": disc.get("url") or "",
                "state": "closed" if disc.get("closed") else "open",
                "updated_at": disc.get("updatedAt"),
            }
        )
    posts.sort(key=lambda p: p.get("updated_at") or "", reverse=True)
    return posts


def _build_posts_index(gh: GitHubClient, token: str) -> None:
    prev = embeddings.load_index(gh, config.POSTS_INDEX_PATH)
    posts = _collect_posts(gh)
    index, changed = embeddings.build_posts_index(
        gh, posts, token=token, previous=prev
    )
    if index is None:
        summary("- posts: build skipped (embeddings unavailable / rate limited)")
        return
    count = len(index.get("posts", []))
    if not changed:
        summary(f"- posts: unchanged ({count} posts); no commit")
        return
    embeddings.save_index(
        gh, config.POSTS_INDEX_PATH, index, message=f"Update posts index ({count} posts)"
    )
    summary(f"- posts: {count} posts indexed")


def cmd_index(gh: GitHubClient, token: str, target: str = "all") -> int:
    summary(f"## RAG index build ({target})\n")
    if target not in ("docs", "posts", "all"):
        log(f"unknown index target: {target} (use docs|posts|all)")
        return 2
    if target in ("docs", "all"):
        _build_docs_index(gh, token)
    if target in ("posts", "all"):
        _build_posts_index(gh, token)
    return 0


def cmd_index_append(gh: GitHubClient, token: str) -> int:
    """Embed a single new issue and upsert it into the posts index."""
    number = int(_env("ISSUE_NUMBER"))
    summary(f"## RAG posts-index append for #{number}\n")
    issue = gh.get_issue(number)
    if "pull_request" in issue:
        summary(f"#{number}: is a pull request; skipping append.")
        return 0
    post = {
        "kind": "issue",
        "number": number,
        "title": issue.get("title") or _env("ISSUE_TITLE"),
        "body": issue.get("body") or _env("ISSUE_BODY"),
        "url": issue.get("html_url") or "",
        "state": issue.get("state"),
        "updated_at": issue.get("updated_at"),
    }
    index, _changed = embeddings.append_post(gh, post, token=token)
    if index is None:
        summary(f"#{number}: append skipped (embeddings unavailable).")
        return 0
    embeddings.save_index(
        gh,
        config.POSTS_INDEX_PATH,
        index,
        message=f"Append issue #{number} to posts index",
    )
    summary(f"#{number}: appended ({len(index.get('posts', []))} posts total).")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        log(
            "usage: python -m ma_triage "
            "{triage|respond|sweep|dispatch|index|index-append}"
        )
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
    if command == "index":
        target = argv[1] if len(argv) > 1 else "all"
        return cmd_index(gh, token, target)
    if command == "index-append":
        return cmd_index_append(gh, token)
    log(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
