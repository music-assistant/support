"""Tests for the `index` and `index-append` subcommands."""

from conftest import FakeGH
from ma_triage import __main__ as main
from ma_triage import config, embeddings
from ma_triage.models import DocChunk


def _chunk(cid, text):
    return DocChunk(
        id=cid, path=cid.split("#")[0], url=f"https://x/{cid}", title="T",
        heading=cid, text=text, breadcrumbs=["T", cid], sha=text,
    )


def _commit_count(gh, path):
    return sum(1 for c in gh.calls if c[0] == "commit_files" and path in c[2])


def test_cmd_index_docs_commits_once_then_skips_unchanged(ai_on, monkeypatch):
    chunks = [_chunk("a#x", "alpha text"), _chunk("b#y", "beta text")]
    monkeypatch.setattr(embeddings.docs, "build_chunks", lambda gh: chunks)
    gh = FakeGH()

    assert main.cmd_index(gh, "t", "docs") == 0
    assert config.DOCS_INDEX_PATH in gh._index_files
    assert _commit_count(gh, config.DOCS_INDEX_PATH) == 1

    # Second run with identical content -> unchanged -> no new commit.
    assert main.cmd_index(gh, "t", "docs") == 0
    assert _commit_count(gh, config.DOCS_INDEX_PATH) == 1


def test_cmd_index_docs_dry_run_makes_no_commit(ai_on, monkeypatch):
    monkeypatch.setattr(embeddings.docs, "build_chunks", lambda gh: [_chunk("a#x", "t")])
    gh = FakeGH()
    gh.dry_run = True
    assert main.cmd_index(gh, "t", "docs") == 0
    # commit_files was invoked but, being dry-run, stored nothing.
    assert any(c[0] == "commit_files" for c in gh.calls)
    assert config.DOCS_INDEX_PATH not in gh._index_files


def test_cmd_index_unknown_target():
    assert main.cmd_index(FakeGH(), "t", "bogus") == 2


# --- the provider is unreachable -------------------------------------------- #
#
# GitHub Models was retired on 2026-07-30. Every nightly build for the sixteen
# days that followed reported success while writing nothing, because an
# unavailable embedder was treated as an acceptable outcome. Producing an index
# is this command's only job, so it must now say when it did not.
def _no_embeddings(monkeypatch):
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts, *, token: None)


def test_cmd_index_fails_when_embeddings_are_unavailable(ai_on, monkeypatch):
    monkeypatch.setattr(embeddings.docs, "build_chunks", lambda gh: [_chunk("a#x", "t")])
    _no_embeddings(monkeypatch)
    gh = FakeGH()
    assert main.cmd_index(gh, "t", "docs") == 1
    assert config.DOCS_INDEX_PATH not in gh._index_files


def test_cmd_index_posts_fails_when_embeddings_are_unavailable(ai_on, monkeypatch):
    _no_embeddings(monkeypatch)
    gh = FakeGH(
        issues=[{"number": 1, "title": "bug", "body": "b", "html_url": "u1",
                 "state": "open", "updated_at": "2024-01-01"}],
    )
    assert main.cmd_index(gh, "t", "posts") == 1
    assert config.POSTS_INDEX_PATH not in gh._index_files


def test_cmd_index_all_fails_if_either_target_fails(ai_on, monkeypatch):
    monkeypatch.setattr(embeddings.docs, "build_chunks", lambda gh: [_chunk("a#x", "t")])
    _no_embeddings(monkeypatch)
    assert main.cmd_index(FakeGH(), "t", "all") == 1


def test_cmd_index_annotates_the_failure(ai_on, monkeypatch, capsys):
    monkeypatch.setattr(embeddings.docs, "build_chunks", lambda gh: [_chunk("a#x", "t")])
    _no_embeddings(monkeypatch)
    main.cmd_index(FakeGH(), "t", "docs")
    assert "::error::" in capsys.readouterr().err


def test_cmd_index_append_annotates_but_does_not_fail_triage(ai_on, monkeypatch, capsys):
    """A provider outage must not mark every incoming issue's workflow red."""
    monkeypatch.setenv("ISSUE_NUMBER", "123")
    _no_embeddings(monkeypatch)
    gh = FakeGH()
    monkeypatch.setattr(
        gh, "get_issue",
        lambda n: {"number": n, "title": "t", "body": "b", "html_url": "u",
                   "state": "open"},
        raising=False,
    )
    assert main.cmd_index_append(gh, "t") == 0
    assert "::error::" in capsys.readouterr().err
    assert config.POSTS_INDEX_PATH not in gh._index_files


def test_cmd_index_append(ai_on, monkeypatch):
    monkeypatch.setenv("ISSUE_NUMBER", "123")
    monkeypatch.setenv("ISSUE_TITLE", "sonos grouping bug")
    monkeypatch.setenv("ISSUE_BODY", "players won't group")
    gh = FakeGH()
    monkeypatch.setattr(
        gh, "get_issue",
        lambda n: {"number": n, "title": "sonos grouping bug",
                   "body": "players won't group", "html_url": "https://x/123",
                   "state": "open"},
        raising=False,
    )
    assert main.cmd_index_append(gh, "t") == 0
    assert config.POSTS_INDEX_PATH in gh._index_files
    import json
    stored = json.loads(gh._index_files[config.POSTS_INDEX_PATH])
    assert [p["number"] for p in stored["posts"]] == [123]


def test_cmd_index_append_skips_pull_requests(ai_on, monkeypatch):
    monkeypatch.setenv("ISSUE_NUMBER", "9")
    gh = FakeGH()
    monkeypatch.setattr(
        gh, "get_issue",
        lambda n: {"number": n, "pull_request": {"url": "x"}},
        raising=False,
    )
    assert main.cmd_index_append(gh, "t") == 0
    assert config.POSTS_INDEX_PATH not in gh._index_files


def test_collect_posts_excludes_translation_discussions():
    gh = FakeGH(
        issues=[{"number": 1, "title": "bug", "body": "b", "html_url": "u1",
                 "state": "open", "updated_at": "2024-01-01"}],
        discussions=[
            {"number": 2, "title": "how do I", "body": "b", "url": "u2",
             "updatedAt": "2024-01-02", "closed": False, "category": {"name": "Q&A"}},
            {"number": 3, "title": "add German", "body": "b", "url": "u3",
             "updatedAt": "2024-01-03", "closed": False,
             "category": {"name": "Translations"}},
        ],
    )
    posts = main._collect_posts(gh)
    keys = {(p["kind"], p["number"]) for p in posts}
    assert ("issue", 1) in keys
    assert ("discussion", 2) in keys
    assert ("discussion", 3) not in keys  # translation category excluded
