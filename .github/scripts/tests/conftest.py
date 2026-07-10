"""Shared pytest fixtures and a network-free fake GitHub client."""

from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

# Make the ma_triage package importable when tests are run from anywhere.
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

# Force deterministic flag state for tests regardless of the environment.
os.environ.setdefault("TRIAGE_DRY_RUN", "false")
os.environ.setdefault("TRIAGE_AI_ENABLED", "false")


class FakeGH:
    """A stand-in for GitHubClient that records mutations and serves canned reads."""

    def __init__(self, *, latest_tag="2.9.5", labels=None, manifests=None):
        self.dry_run = False
        self.repo = "music-assistant/support"
        self._latest_tag = latest_tag
        self._labels = set(labels or [])
        self._manifests = manifests or {}
        self._comments: list[dict] = []
        self.calls: list[tuple] = []

    # reads -----------------------------------------------------------------
    def get_latest_release(self, repo="music-assistant/server"):
        return {"tag_name": self._latest_tag} if self._latest_tag else None

    def get_raw_file(self, repo, path, ref="main"):
        for domain, content in self._manifests.items():
            if f"/{domain}/" in path:
                return json.dumps(content)
        return None

    def list_labels(self):
        return set(self._labels)

    def search_issues(self, query, per_page=10):
        return {"total_count": 0, "items": []}

    def list_comments(self, number):
        return list(self._comments)

    def get_issue(self, number):
        return {"number": number, "labels": [], "user": {"login": "reporter"}}

    # mutations (recorded) --------------------------------------------------
    def add_labels(self, number, labels):
        self.calls.append(("add_labels", number, tuple(labels)))

    def remove_label(self, number, label):
        self.calls.append(("remove_label", number, label))

    def create_comment(self, number, body):
        self.calls.append(("create_comment", number, body))
        self._comments.append({"id": len(self._comments) + 1, "body": body,
                               "user": {"login": "bot", "type": "Bot"}})

    def update_comment(self, comment_id, body):
        self.calls.append(("update_comment", comment_id, body))

    def add_assignees(self, number, assignees):
        self.calls.append(("add_assignees", number, tuple(assignees)))

    def close_issue(self, number, reason="not_planned"):
        self.calls.append(("close_issue", number, reason))

    def list_issues_with_label(self, label, state="open"):
        return []


@pytest.fixture
def fake_gh():
    return FakeGH(
        labels={"sonos", "snapcast", "spotify", "Chromecast", "airplay",
                "needs-attention", "waiting-for-user", "triage/needs-diagnostics"},
        manifests={
            "sonos": {"codeowners": ["@music-assistant"]},
            "snapcast": {"codeowners": ["@SantiagoSotoC", "@music-assistant"]},
        },
    )


@pytest.fixture
def sample_raw():
    return (FIXTURES / "sample-diagnostics.json").read_bytes()


@pytest.fixture
def injection_raw():
    return (FIXTURES / "injection-diagnostics.json").read_bytes()


@pytest.fixture
def sample_log():
    return (FIXTURES / "sample.log").read_bytes()
