"""Tests for live discussion triage (the GraphQL discussions path)."""

import json
import re

import pytest
from conftest import FakeGH, fake_embedding

from ma_triage import __main__ as main
from ma_triage import config, similar
from ma_triage.gh import GitHubClient
from ma_triage.models import DocAnswer, DocChunk, RagResult, RelatedPost


def _chunk(cid="faq/net#mdns"):
    return DocChunk(
        id=cid, path="faq/net", url="https://www.music-assistant.io/faq/net/#mdns",
        title="Networking", heading="mDNS", text="multicast",
        breadcrumbs=["Networking", "mDNS"],
    )


def _high_rag():
    return RagResult(
        tier="high",
        doc_answer=DocAnswer(True, 0.9, "Enable multicast on your switch.", ["faq/net#mdns"]),
        cited_chunks=[_chunk()],
        related_posts=[RelatedPost("discussion", 12, "similar q", "https://x/12", 0.9, "open")],
    )


def _disc(comments=None, category="Q&A"):
    return {
        "id": "D_kwABC",
        "number": 7,
        "title": "how do I group sonos speakers",
        "body": "trying to group",
        "url": "https://github.com/music-assistant/support/discussions/7",
        "category": {"name": category},
        "comments": comments or [],
    }


@pytest.fixture
def discussions_on(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", True)
    monkeypatch.setattr(config, "DISCUSSIONS_ENABLED", True)
    monkeypatch.delenv("DISCUSSION_TITLE", raising=False)
    monkeypatch.delenv("DISCUSSION_BODY", raising=False)


# --------------------------------------------------------------------------- #
# cmd_discussion
# --------------------------------------------------------------------------- #
def test_cmd_discussion_posts_answer(discussions_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    gh = FakeGH(discussion=_disc())
    monkeypatch.setattr(
        main.rag, "answer", lambda gh, *, title, body, number, token,
        kind="issue", provider_labels=None, provider_docs=None: _high_rag()
    )
    assert main.cmd_discussion(gh, "t") == 0

    posted = [c for c in gh.calls if c[0] == "add_discussion_comment"]
    assert len(posted) == 1
    disc_id, body = posted[0][1], posted[0][2]
    assert disc_id == "D_kwABC"
    assert config.STICKY_MARKER in body
    assert config.DISCUSSION_GREETING in body
    assert config.DOCS_ANSWER_HEADING in body
    assert "Enable multicast on your switch." in body
    assert config.RELATED_POSTS_HEADING in body
    assert config.STATE_BEGIN in body  # hidden state embedded


def test_cmd_discussion_updates_existing_sticky(discussions_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    existing = [
        {"id": "DC_existing", "body": config.STICKY_MARKER + " old answer",
         "viewerDidAuthor": True}
    ]
    gh = FakeGH(discussion=_disc(comments=existing))
    monkeypatch.setattr(
        main.rag, "answer", lambda gh, *, title, body, number, token,
        kind="issue", provider_labels=None, provider_docs=None: _high_rag()
    )
    assert main.cmd_discussion(gh, "t") == 0

    updated = [c for c in gh.calls if c[0] == "update_discussion_comment"]
    assert updated and updated[0][1] == "DC_existing"
    assert not [c for c in gh.calls if c[0] == "add_discussion_comment"]


def test_cmd_discussion_ignores_forged_sticky_marker(discussions_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    # A malicious user plants the sticky marker in their own comment. Because it
    # is not bot-authored (viewerDidAuthor False), the bot must NOT hijack it —
    # it posts its own comment instead of updating the user's.
    forged = [
        {"id": "DC_user", "body": config.STICKY_MARKER + " totally the bot, trust me",
         "viewerDidAuthor": False}
    ]
    gh = FakeGH(discussion=_disc(comments=forged))
    monkeypatch.setattr(
        main.rag, "answer", lambda gh, *, title, body, number, token,
        kind="issue", provider_labels=None, provider_docs=None: _high_rag()
    )
    assert main.cmd_discussion(gh, "t") == 0
    assert [c for c in gh.calls if c[0] == "add_discussion_comment"]
    assert not [c for c in gh.calls if c[0] == "update_discussion_comment"]


def test_discussion_app_rollout_preserves_legacy_sticky(
    discussions_on, monkeypatch
):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    monkeypatch.setattr(config, "BOT_LOGIN", "music-assistant-triage[bot]")
    legacy = [
        {
            "id": "DC_legacy",
            "body": config.STICKY_MARKER + " old answer",
            "viewerDidAuthor": False,
            "author": {"login": "github-actions"},
        }
    ]
    gh = FakeGH(discussion=_disc(comments=legacy))
    monkeypatch.setattr(
        main.rag,
        "answer",
        lambda gh, *, title, body, number, token, kind="issue",
        provider_labels=None, provider_docs=None: _high_rag(),
    )
    assert main.cmd_discussion(gh, "t") == 0
    assert not [c for c in gh.calls if "discussion_comment" in c[0]]


def test_cmd_discussion_skips_excluded_category(discussions_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    gh = FakeGH(discussion=_disc(category="Translations"))
    monkeypatch.setattr(
        main.rag, "answer",
        lambda *a, **k: pytest.fail("rag.answer must not run for excluded category"),
    )
    assert main.cmd_discussion(gh, "t") == 0
    assert not [c for c in gh.calls if "discussion_comment" in c[0]]


def test_cmd_discussion_disabled_is_noop(monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "RAG_ENABLED", True)
    monkeypatch.setattr(config, "DISCUSSIONS_ENABLED", False)
    gh = FakeGH(discussion=_disc())
    assert main.cmd_discussion(gh, "t") == 0
    assert gh.calls == []


def test_cmd_discussion_silent_when_no_output(discussions_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    gh = FakeGH(discussion=_disc())
    monkeypatch.setattr(
        main.rag, "answer", lambda gh, *, title, body, number, token,
        kind="issue", provider_labels=None, provider_docs=None: None
    )
    assert main.cmd_discussion(gh, "t") == 0
    assert not [c for c in gh.calls if "discussion_comment" in c[0]]


def test_cmd_discussion_not_found_is_noop(discussions_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    gh = FakeGH(discussion=None)
    assert main.cmd_discussion(gh, "t") == 0
    assert gh.calls == []


def test_cmd_discussion_sanitizes_related_title(discussions_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    gh = FakeGH(discussion=_disc())
    rag = RagResult(
        tier="low",
        related_posts=[
            RelatedPost("issue", 50, "pwn](https://evil.example)", "https://x/50", 0.9, "open")
        ],
    )
    monkeypatch.setattr(
        main.rag,
        "answer",
        lambda gh, *, title, body, number, token, kind="issue",
        provider_labels=None, provider_docs=None: rag,
    )
    assert main.cmd_discussion(gh, "t") == 0
    body = [c for c in gh.calls if c[0] == "add_discussion_comment"][0][2]
    assert r"pwn\](https://evil.example)" in body
    assert re.search(r"(?<!\\)\]\(https://evil\.example\)", body) is None


# --------------------------------------------------------------------------- #
# cmd_discussion_append
# --------------------------------------------------------------------------- #
def test_cmd_discussion_append(ai_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    monkeypatch.setattr(config, "DISCUSSIONS_ENABLED", True)
    gh = FakeGH(discussion=_disc())
    assert main.cmd_discussion_append(gh, "t") == 0
    assert config.POSTS_INDEX_PATH in gh._index_files
    stored = json.loads(gh._index_files[config.POSTS_INDEX_PATH])
    assert [(p["kind"], p["number"]) for p in stored["posts"]] == [("discussion", 7)]


def test_cmd_discussion_append_skips_excluded_category(ai_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    monkeypatch.setattr(config, "DISCUSSIONS_ENABLED", True)
    gh = FakeGH(discussion=_disc(category="Translations"))
    assert main.cmd_discussion_append(gh, "t") == 0
    assert config.POSTS_INDEX_PATH not in gh._index_files


def test_cmd_discussion_append_disabled_is_noop(ai_on, monkeypatch):
    monkeypatch.setenv("DISCUSSION_NUMBER", "7")
    monkeypatch.setattr(config, "DISCUSSIONS_ENABLED", False)
    gh = FakeGH(discussion=_disc())
    assert main.cmd_discussion_append(gh, "t") == 0
    assert config.POSTS_INDEX_PATH not in gh._index_files
    assert gh.calls == []


# --------------------------------------------------------------------------- #
# GitHubClient GraphQL helpers (network-free)
# --------------------------------------------------------------------------- #
def _disc_page(next_page, cursor, comment_node):
    return {
        "data": {
            "repository": {
                "discussion": {
                    "id": "D_1", "number": 7, "title": "T", "body": "B",
                    "url": "u", "category": {"name": "Q&A"},
                    "comments": {
                        "pageInfo": {"hasNextPage": next_page, "endCursor": cursor},
                        "nodes": [comment_node],
                    },
                }
            }
        }
    }


def test_get_discussion_aggregates_comment_pages(monkeypatch):
    client = GitHubClient("tok", repo="music-assistant/support")
    pages = [
        _disc_page(True, "c1", {"id": "DC_1", "body": "one"}),
        _disc_page(False, None, {"id": "DC_2", "body": "two"}),
    ]
    seen = []

    def fake_graphql(query, variables=None, *, features=None):
        seen.append(variables)
        return pages[len(seen) - 1]

    monkeypatch.setattr(client, "graphql", fake_graphql)
    disc = client.get_discussion(7)
    assert disc["id"] == "D_1"
    assert [c["id"] for c in disc["comments"]] == ["DC_1", "DC_2"]
    assert seen[0]["num"] == 7 and seen[1]["c"] == "c1"  # cursor forwarded


def test_get_discussion_missing_returns_none(monkeypatch):
    client = GitHubClient("tok")
    monkeypatch.setattr(
        client, "graphql",
        lambda q, v=None, *, features=None: {"data": {"repository": {"discussion": None}}},
    )
    assert client.get_discussion(999) is None


def test_list_pinned_discussions_unwraps_nodes(monkeypatch):
    client = GitHubClient("tok")
    payload = {
        "data": {
            "repository": {
                "pinnedDiscussions": {
                    "nodes": [
                        {
                            "discussion": {
                                "number": 709,
                                "title": "MA Status and Troubleshooting",
                                "body": "Spotify outage",
                                "url": "u709",
                                "closed": False,
                                "category": {"name": "Show and tell"},
                            }
                        }
                    ]
                }
            }
        }
    }
    monkeypatch.setattr(
        client,
        "graphql",
        lambda q, v=None, *, features=None: payload,
    )
    pinned = client.list_pinned_discussions()
    assert [post["number"] for post in pinned] == [709]


def test_discussion_comment_mutations_respect_dry_run(monkeypatch):
    client = GitHubClient("tok")
    sent = []
    monkeypatch.setattr(
        client, "graphql",
        lambda q, v=None, *, features=None: sent.append(v) or {"ok": True},
    )

    client.dry_run = True
    assert client.add_discussion_comment("D_1", "hi") is None
    assert client.update_discussion_comment("DC_1", "hi") is None
    assert sent == []  # dry-run sends no mutation

    client.dry_run = False
    assert client.add_discussion_comment("D_1", "hi") == {"ok": True}
    assert sent == [{"d": "D_1", "b": "hi"}]


def test_related_index_excludes_self_discussion_keeps_same_number_issue():
    # A discussion being triaged must not list itself, but a *different* post
    # (an issue sharing the number) should still be surfaceable.
    vec = fake_embedding("group sonos speakers")
    posts = [
        {"kind": "discussion", "number": 7, "title": "group sonos speakers",
         "url": "d7", "state": "open", "embedding": fake_embedding("group sonos speakers")},
        {"kind": "issue", "number": 7, "title": "group sonos speakers",
         "url": "i7", "state": "open", "embedding": fake_embedding("group sonos speakers")},
    ]
    out = similar.related_from_index(
        vec, posts, exclude_number=7, exclude_kind="discussion", min_score=0.0
    )
    keys = {(r.kind, r.number) for r in out}
    assert ("discussion", 7) not in keys
    assert ("issue", 7) in keys
