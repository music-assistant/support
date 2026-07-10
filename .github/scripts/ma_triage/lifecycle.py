"""Issue lifecycle: response-state labels + reminder/auto-close cadence.

Two entry points:
* :func:`on_comment` — reacts to a new (non-bot) comment, flipping the
  ``needs-attention`` / ``waiting-for-user`` state and clearing reminder labels
  when the reporter replies.
* :func:`sweep` — a scheduled pass over ``waiting-for-user`` issues that sends a
  gentle reminder (3d), a close warning (7d) and finally auto-closes (14d) based
  on days since the reporter was last active.

All mutations go through the dry-run-aware :class:`GitHubClient`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import config
from .gh import GitHubClient, summary

# Author associations that we treat as "a maintainer / team member replied".
_MAINTAINER_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def days_since(value: str | None) -> float:
    ts = _parse_ts(value)
    if ts is None:
        return 0.0
    return (_now() - ts).total_seconds() / 86400.0


def issue_labels(issue: dict[str, Any]) -> set[str]:
    return {lbl["name"] for lbl in issue.get("labels", []) if isinstance(lbl, dict)}


def is_exempt(labels: set[str]) -> bool:
    """Issues a human has engaged with are never auto-nudged/closed."""
    return bool(labels & config.EXEMPT_LABELS) or config.LABEL_SKIP in labels


def _is_bot_comment(comment: dict[str, Any]) -> bool:
    body = comment.get("body") or ""
    if config.STICKY_MARKER in body or config.REMINDER_MARKER in body:
        return True
    user = comment.get("user") or {}
    if user.get("type") == "Bot":
        return True
    login = user.get("login") or ""
    return login.endswith("[bot]")


def last_user_activity(issue: dict[str, Any], comments: list[dict[str, Any]]) -> str | None:
    """Timestamp of the reporter's most recent activity (issue or a comment)."""
    latest = issue.get("created_at")
    for comment in comments:
        if _is_bot_comment(comment):
            continue
        created = comment.get("created_at")
        if created and (latest is None or created > latest):
            latest = created
    return latest


# --------------------------------------------------------------------------- #
# Comment-driven state transitions
# --------------------------------------------------------------------------- #
def on_comment(
    gh: GitHubClient,
    issue: dict[str, Any],
    *,
    actor_login: str,
    author_association: str,
) -> None:
    """Update response-state labels when a non-bot comment is posted."""
    number = issue["number"]
    labels = issue_labels(issue)
    if config.LABEL_HOLD in labels or config.LABEL_SKIP in labels:
        summary(f"#{number}: automation paused (hold/skip label); no state change.")
        return

    reporter = (issue.get("user") or {}).get("login")
    is_reporter = actor_login == reporter

    if is_reporter:
        # The reporter responded → back into the maintainers' court.
        for lbl in (
            config.LABEL_WAITING_FOR_USER,
            config.LABEL_REMINDED_1,
            config.LABEL_REMINDED_2,
            config.LABEL_STALE,
        ):
            if lbl in labels:
                gh.remove_label(number, lbl)
        if config.LABEL_NEEDS_ATTENTION not in labels:
            gh.add_labels(number, [config.LABEL_NEEDS_ATTENTION])
    elif author_association in _MAINTAINER_ASSOCIATIONS:
        # A maintainer replied → typically now waiting on the reporter.
        if config.LABEL_NEEDS_ATTENTION in labels:
            gh.remove_label(number, config.LABEL_NEEDS_ATTENTION)
        if config.LABEL_WAITING_FOR_USER not in labels:
            gh.add_labels(number, [config.LABEL_WAITING_FOR_USER])


# --------------------------------------------------------------------------- #
# Scheduled sweep
# --------------------------------------------------------------------------- #
def _post_reminder(gh: GitHubClient, number: int, message: str) -> None:
    gh.create_comment(number, f"{config.REMINDER_MARKER}\n\n{message}{config.DISCLOSURE_FOOTER}")


def sweep_issue(gh: GitHubClient, issue: dict[str, Any]) -> str:
    """Apply the reminder/close cadence to a single waiting issue.

    Returns a short human-readable description of the action taken (for the
    job summary / tests).
    """
    number = issue["number"]
    labels = issue_labels(issue)
    if is_exempt(labels):
        return f"#{number}: exempt, skipped"

    comments = gh.list_comments(number)
    idle = days_since(last_user_activity(issue, comments))

    if idle >= config.AUTO_CLOSE_DAYS:
        gh.create_comment(
            number, f"{config.REMINDER_MARKER}\n\n{config.AUTO_CLOSE_MESSAGE}{config.DISCLOSURE_FOOTER}"
        )
        gh.add_labels(number, [config.LABEL_AUTO_CLOSED])
        gh.close_issue(number, reason="not_planned")
        return f"#{number}: auto-closed after {idle:.1f}d idle"

    if idle >= config.REMINDER_2_DAYS and config.LABEL_REMINDED_2 not in labels:
        _post_reminder(
            gh, number, config.REMINDER_2_MESSAGE.format(days=config.AUTO_CLOSE_DAYS)
        )
        gh.add_labels(number, [config.LABEL_REMINDED_2])
        return f"#{number}: sent close-warning ({idle:.1f}d idle)"

    if idle >= config.REMINDER_1_DAYS and config.LABEL_REMINDED_1 not in labels:
        _post_reminder(gh, number, config.REMINDER_1_MESSAGE)
        gh.add_labels(number, [config.LABEL_REMINDED_1])
        return f"#{number}: sent gentle reminder ({idle:.1f}d idle)"

    return f"#{number}: nothing due ({idle:.1f}d idle)"


def sweep(gh: GitHubClient) -> list[str]:
    """Run the cadence over every open ``waiting-for-user`` issue."""
    issues = gh.list_issues_with_label(config.LABEL_WAITING_FOR_USER, state="open")
    summary(f"Sweep: {len(issues)} issue(s) in '{config.LABEL_WAITING_FOR_USER}'")
    results = []
    for issue in issues:
        result = sweep_issue(gh, issue)
        results.append(result)
        summary(f"- {result}")
    return results
