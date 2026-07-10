from datetime import datetime, timedelta, timezone

from ma_triage import config, lifecycle


def _iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _issue(number=1, labels=(), reporter="reporter", created_days_ago=0):
    return {
        "number": number,
        "labels": [{"name": n} for n in labels],
        "user": {"login": reporter},
        "created_at": _iso(created_days_ago),
    }


def test_reporter_comment_marks_needs_attention(fake_gh):
    issue = _issue(labels=[config.LABEL_WAITING_FOR_USER, config.LABEL_REMINDED_1])
    lifecycle.on_comment(fake_gh, issue, actor_login="reporter",
                         author_association="NONE")
    removed = {c[2] for c in fake_gh.calls if c[0] == "remove_label"}
    added = {lbl for c in fake_gh.calls if c[0] == "add_labels" for lbl in c[2]}
    assert config.LABEL_WAITING_FOR_USER in removed
    assert config.LABEL_REMINDED_1 in removed
    assert config.LABEL_NEEDS_ATTENTION in added


def test_maintainer_comment_marks_waiting(fake_gh):
    issue = _issue(labels=[config.LABEL_NEEDS_ATTENTION])
    lifecycle.on_comment(fake_gh, issue, actor_login="maintainer",
                         author_association="MEMBER")
    removed = {c[2] for c in fake_gh.calls if c[0] == "remove_label"}
    added = {lbl for c in fake_gh.calls if c[0] == "add_labels" for lbl in c[2]}
    assert config.LABEL_NEEDS_ATTENTION in removed
    assert config.LABEL_WAITING_FOR_USER in added


def test_hold_label_pauses(fake_gh):
    issue = _issue(labels=[config.LABEL_HOLD])
    lifecycle.on_comment(fake_gh, issue, actor_login="reporter",
                         author_association="NONE")
    assert fake_gh.calls == []


def test_sweep_gentle_reminder(fake_gh):
    issue = _issue(created_days_ago=4, labels=[config.LABEL_WAITING_FOR_USER])
    msg = lifecycle.sweep_issue(fake_gh, issue)
    assert "gentle reminder" in msg
    added = {lbl for c in fake_gh.calls if c[0] == "add_labels" for lbl in c[2]}
    assert config.LABEL_REMINDED_1 in added


def test_sweep_close_warning(fake_gh):
    issue = _issue(created_days_ago=8,
                   labels=[config.LABEL_WAITING_FOR_USER, config.LABEL_REMINDED_1])
    msg = lifecycle.sweep_issue(fake_gh, issue)
    assert "close-warning" in msg
    added = {lbl for c in fake_gh.calls if c[0] == "add_labels" for lbl in c[2]}
    assert config.LABEL_REMINDED_2 in added


def test_sweep_auto_close(fake_gh):
    issue = _issue(created_days_ago=20,
                   labels=[config.LABEL_WAITING_FOR_USER, config.LABEL_REMINDED_2])
    msg = lifecycle.sweep_issue(fake_gh, issue)
    assert "auto-closed" in msg
    assert any(c[0] == "close_issue" for c in fake_gh.calls)


def test_sweep_exempts_bug(fake_gh):
    issue = _issue(created_days_ago=30,
                   labels=[config.LABEL_WAITING_FOR_USER, "bug"])
    msg = lifecycle.sweep_issue(fake_gh, issue)
    assert "exempt" in msg
    assert fake_gh.calls == []


def test_sweep_nothing_due(fake_gh):
    issue = _issue(created_days_ago=1, labels=[config.LABEL_WAITING_FOR_USER])
    msg = lifecycle.sweep_issue(fake_gh, issue)
    assert "nothing due" in msg
