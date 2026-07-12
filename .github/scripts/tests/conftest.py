"""Shared pytest fixtures and a network-free fake GitHub client."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys

import pytest

# Make the ma_triage package importable when tests are run from anywhere.
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

# Force deterministic flag state for tests regardless of the environment.
os.environ.setdefault("TRIAGE_DRY_RUN", "false")
os.environ.setdefault("TRIAGE_AI_ENABLED", "false")

# Small embedding dimension used by the deterministic fake embedder below.
FAKE_DIM = 16


def fake_embedding(text: str | None, dim: int = FAKE_DIM) -> list[float]:
    """Deterministic bag-of-tokens embedding for offline tests.

    Texts that share tokens get a higher cosine similarity, so retrieval /
    related-post ordering is meaningful without any network calls.
    """
    vec = [0.0] * dim
    for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % dim
        vec[idx] += 1.0
    return vec



class FakeGH:
    """A stand-in for GitHubClient that records mutations and serves canned reads."""

    def __init__(self, *, latest_tag="2.9.5", labels=None, manifests=None,
                 index_files=None, tree=None, issues=None, discussions=None,
                 search_items=None, discussion=None, pinned_discussions=None):
        self.dry_run = False
        self.repo = "music-assistant/support"
        self._latest_tag = latest_tag
        self._labels = set(labels or [])
        self._manifests = manifests or {}
        self._comments: list[dict] = []
        self._index_files: dict[str, str] = dict(index_files or {})
        self._tree = list(tree or [])
        self._issues = list(issues or [])
        self._discussions = list(discussions or [])
        self._pinned_discussions = list(pinned_discussions or [])
        self._discussion_obj = discussion
        self._search_items = list(search_items or [])
        self.calls: list[tuple] = []

    # reads -----------------------------------------------------------------
    def get_latest_release(self, repo="music-assistant/server"):
        return {"tag_name": self._latest_tag} if self._latest_tag else None

    def get_raw_file(self, repo, path, ref="main"):
        if path in self._index_files:
            return self._index_files[path]
        for domain, content in self._manifests.items():
            if f"/{domain}/" in path:
                return json.dumps(content)
        return None

    def get_tree(self, repo, ref="main", *, recursive=True):
        return list(self._tree)

    def get_ref_sha(self, branch, *, repo=None):
        return None

    def list_labels(self):
        return set(self._labels)

    def search_issues(self, query, per_page=10):
        return {"total_count": len(self._search_items),
                "items": list(self._search_items)[:per_page]}

    def list_comments(self, number):
        return list(self._comments)

    def get_issue(self, number):
        return {"number": number, "labels": [], "user": {"login": "reporter"}}

    def list_recent_issues(self, *, state="all", limit=500):
        return list(self._issues)[:limit]

    def list_discussions(self, *, limit=500):
        return list(self._discussions)[:limit]

    def list_pinned_discussions(self):
        return list(self._pinned_discussions)

    def get_discussion(self, number):
        return self._discussion_obj

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

    def add_discussion_comment(self, discussion_id, body):
        self.calls.append(("add_discussion_comment", discussion_id, body))

    def update_discussion_comment(self, comment_id, body):
        self.calls.append(("update_discussion_comment", comment_id, body))

    def add_assignees(self, number, assignees):
        self.calls.append(("add_assignees", number, tuple(assignees)))

    def close_issue(self, number, reason="not_planned"):
        self.calls.append(("close_issue", number, reason))

    def list_issues_with_label(self, label, state="open"):
        return []

    def commit_files(self, branch, files, message, *, repo=None):
        self.calls.append(("commit_files", branch, tuple(sorted(files)), message))
        if self.dry_run:
            return None
        self._index_files.update(files)
        return "deadbeef"


@pytest.fixture
def fake_gh():
    return FakeGH(
        labels={"sonos", "snapcast", "spotify", "subsonic", "Chromecast", "airplay",
                "needs-attention", "waiting-for-user", "triage/needs-diagnostics"},
        manifests={
            "sonos": {"codeowners": ["@music-assistant"]},
            "snapcast": {"codeowners": ["@SantiagoSotoC", "@music-assistant"]},
            "opensubsonic": {
                "name": "OpenSubsonic Media Server Library",
                "codeowners": ["@khers"],
                "documentation": "https://music-assistant.io/music-providers/subsonic/",
            },
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


@pytest.fixture
def fake_embed():
    """The deterministic embedding function (see :func:`fake_embedding`)."""
    return fake_embedding


@pytest.fixture
def ai_on(monkeypatch):
    """Enable the RAG layer with a small dim and a deterministic embedder.

    Patches the embeddings client so no network is touched; returns the
    ``fake_embedding`` helper so tests can build matching index vectors.
    """
    from ma_triage import config, embeddings

    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", True)
    monkeypatch.setattr(config, "EMBED_DIM", FAKE_DIM)
    monkeypatch.setattr(
        embeddings,
        "embed_texts",
        lambda texts, *, token: [fake_embedding(t) for t in texts],
    )
    return fake_embedding
