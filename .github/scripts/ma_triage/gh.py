"""Thin GitHub REST + GraphQL client used by every subcommand.

Design goals:
* No heavyweight SDK — just ``requests`` — so behaviour is fully auditable.
* **Dry-run aware**: every *mutating* call is a no-op that logs its intent when
  ``config.DRY_RUN`` is set, so the bot is always safe to run against real issues.
* Retries transient failures with simple backoff.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import requests

from . import config

API_ROOT = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
RAW_ROOT = "https://raw.githubusercontent.com"


def log(msg: str) -> None:
    """Print to stderr so it shows up in the Actions log immediately."""
    print(msg, file=sys.stderr, flush=True)


def summary(msg: str) -> None:
    """Append a line to the GitHub Actions job summary, if available."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(msg + "\n")
        except OSError:
            pass
    log(msg)


class GitHubClient:
    """Minimal GitHub API wrapper with retries and dry-run support."""

    def __init__(
        self,
        token: str,
        repo: str = config.SUPPORT_REPO,
        *,
        dry_run: bool | None = None,
        timeout: int = 30,
    ) -> None:
        self.repo = repo
        self.timeout = timeout
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ma-triage-bot",
            }
        )

    # ------------------------------------------------------------------ #
    # Low-level request with retry/backoff
    # ------------------------------------------------------------------ #
    def _request(
        self, method: str, url: str, *, retries: int = 3, **kwargs: Any
    ) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self._session.request(
                    method, url, timeout=self.timeout, **kwargs
                )
                # Retry on transient server errors / secondary rate limits.
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"{resp.status_code}", response=resp)
                return resp
            except (requests.RequestException, requests.HTTPError) as exc:
                last_exc = exc
                if attempt == retries - 1:
                    break
                time.sleep(2**attempt)
        raise RuntimeError(f"Request failed after {retries} attempts: {last_exc}")

    def _rest(self, method: str, path: str, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{API_ROOT}{path}"
        resp = self._request(method, url, **kwargs)
        if resp.status_code >= 400:
            log(f"! {method} {url} -> {resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()
        if resp.content and "application/json" in resp.headers.get("Content-Type", ""):
            return resp.json()
        return resp.text

    # ------------------------------------------------------------------ #
    # GraphQL
    # ------------------------------------------------------------------ #
    def graphql(
        self, query: str, variables: dict[str, Any] | None = None, *, features: str | None = None
    ) -> dict[str, Any]:
        headers = {}
        if features:
            headers["GraphQL-Features"] = features
        resp = self._request(
            "POST",
            GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            headers=headers,
        )
        data = resp.json()
        if "errors" in data:
            log(f"! GraphQL errors: {data['errors']}")
        return data

    # ------------------------------------------------------------------ #
    # Read helpers (always executed, even in dry-run)
    # ------------------------------------------------------------------ #
    def get_issue(self, number: int) -> dict[str, Any]:
        return self._rest("GET", f"/repos/{self.repo}/issues/{number}")

    def list_comments(self, number: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._rest(
                "GET",
                f"/repos/{self.repo}/issues/{number}/comments",
                params={"per_page": 100, "page": page},
            )
            if not batch:
                break
            comments.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return comments

    def list_events(self, number: int) -> list[dict[str, Any]]:
        return self._rest(
            "GET",
            f"/repos/{self.repo}/issues/{number}/events",
            params={"per_page": 100},
        )

    def search_issues(self, query: str, *, per_page: int = 10) -> dict[str, Any]:
        return self._rest(
            "GET", "/search/issues", params={"q": query, "per_page": per_page}
        )

    def list_labels(self) -> set[str]:
        """Return the set of label names that exist in the repo."""
        names: set[str] = set()
        page = 1
        while True:
            batch = self._rest(
                "GET",
                f"/repos/{self.repo}/labels",
                params={"per_page": 100, "page": page},
            )
            if not batch:
                break
            names.update(lbl["name"] for lbl in batch if isinstance(lbl, dict))
            if len(batch) < 100:
                break
            page += 1
        return names

    def list_issues_with_label(self, label: str, *, state: str = "open") -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._rest(
                "GET",
                f"/repos/{self.repo}/issues",
                params={
                    "labels": label,
                    "state": state,
                    "per_page": 100,
                    "page": page,
                },
            )
            if not batch:
                break
            # The issues endpoint returns PRs too; filter them out.
            issues.extend(i for i in batch if "pull_request" not in i)
            if len(batch) < 100:
                break
            page += 1
        return issues

    def get_latest_release(self, repo: str = config.SERVER_REPO) -> dict[str, Any] | None:
        try:
            return self._rest("GET", f"/repos/{repo}/releases/latest")
        except Exception as exc:  # noqa: BLE001
            log(f"Could not fetch latest release: {exc}")
            return None

    def get_raw_file(self, repo: str, path: str, ref: str = "main") -> str | None:
        url = f"{RAW_ROOT}/{repo}/{ref}/{path}"
        try:
            resp = self._request("GET", url)
            if resp.status_code == 200:
                return resp.text
        except Exception as exc:  # noqa: BLE001
            log(f"Could not fetch {url}: {exc}")
        return None

    def get_tree(
        self, repo: str, ref: str = "main", *, recursive: bool = True
    ) -> list[dict[str, Any]]:
        """List a repo's git tree (used to enumerate the docs corpus).

        ``ref`` may be a branch name or tree SHA. Returns the ``tree`` array of
        ``{path, type, sha, ...}`` entries, or ``[]`` on any error.
        """
        params = {"recursive": "1"} if recursive else {}
        try:
            data = self._rest("GET", f"/repos/{repo}/git/trees/{ref}", params=params)
        except Exception as exc:  # noqa: BLE001
            log(f"Could not fetch tree {repo}@{ref}: {exc}")
            return []
        if isinstance(data, dict):
            tree = data.get("tree")
            if isinstance(tree, list):
                return tree
        return []

    def get_ref_sha(self, branch: str, *, repo: str | None = None) -> str | None:
        """Return the commit SHA a branch points at, or ``None`` if it is absent."""
        repo = repo or self.repo
        try:
            data = self._rest("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            raise
        if isinstance(data, dict):
            return (data.get("object") or {}).get("sha")
        return None

    def list_recent_issues(
        self, *, state: str = "all", limit: int = 500
    ) -> list[dict[str, Any]]:
        """Recent issues (newest-updated first), excluding pull requests."""
        out: list[dict[str, Any]] = []
        page = 1
        while len(out) < limit:
            batch = self._rest(
                "GET",
                f"/repos/{self.repo}/issues",
                params={
                    "state": state,
                    "per_page": 100,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            if not batch:
                break
            for issue in batch:
                if "pull_request" in issue:
                    continue
                out.append(issue)
                if len(out) >= limit:
                    break
            if len(batch) < 100:
                break
            page += 1
        return out

    def list_discussions(self, *, limit: int = 500) -> list[dict[str, Any]]:
        """Recent discussions via GraphQL (empty list if disabled/unavailable)."""
        owner, name = self.repo.split("/", 1)
        query = """
        query($o:String!,$n:String!,$c:String){
          repository(owner:$o,name:$n){
            discussions(first:100, after:$c,
              orderBy:{field:UPDATED_AT, direction:DESC}){
              pageInfo{ hasNextPage endCursor }
              nodes{ number title body url updatedAt closed category { name } }
            }
          }
        }
        """
        out: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(out) < limit:
            try:
                data = self.graphql(query, {"o": owner, "n": name, "c": cursor})
            except Exception as exc:  # noqa: BLE001
                log(f"Discussion listing failed: {exc}")
                break
            repo = (data.get("data") or {}).get("repository") or {}
            disc = repo.get("discussions") or {}
            nodes = disc.get("nodes") or []
            out.extend(n for n in nodes if isinstance(n, dict))
            page_info = disc.get("pageInfo") or {}
            if not page_info.get("hasNextPage") or not nodes:
                break
            cursor = page_info.get("endCursor")
        return out[:limit]

    def list_pinned_discussions(self) -> list[dict[str, Any]]:
        """Pinned support Discussions (empty list if unavailable)."""
        owner, name = self.repo.split("/", 1)
        query = """
        query($o:String!,$n:String!){
          repository(owner:$o,name:$n){
            pinnedDiscussions(first:50){
              nodes{
                discussion{
                  number title body url closed category { name }
                }
              }
            }
          }
        }
        """
        try:
            data = self.graphql(query, {"o": owner, "n": name})
        except Exception as exc:  # noqa: BLE001
            log(f"Pinned discussion listing failed: {exc}")
            return []
        repo = (data.get("data") or {}).get("repository") or {}
        connection = repo.get("pinnedDiscussions") or {}
        discussions: list[dict[str, Any]] = []
        for node in connection.get("nodes") or []:
            discussion = node.get("discussion") if isinstance(node, dict) else None
            if isinstance(discussion, dict):
                discussions.append(discussion)
        return discussions

    def get_discussion(self, number: int) -> dict[str, Any] | None:
        """Fetch one discussion + all its comment ids/bodies via GraphQL.

        Discussions are GraphQL-only (no REST). Returns a normalized dict
        ``{id, number, title, body, url, category, comments}`` where each comment
        is ``{id, body}`` (the node id is needed to update the sticky comment in
        place). Returns ``None`` when the discussion can't be read (Discussions
        disabled, not found, or an API error) so callers degrade to a no-op.
        """
        owner, name = self.repo.split("/", 1)
        query = """
        query($o:String!,$n:String!,$num:Int!,$c:String){
          repository(owner:$o,name:$n){
            discussion(number:$num){
              id number title body url
              category { name }
              comments(first:100, after:$c){
                pageInfo{ hasNextPage endCursor }
                nodes{ id body viewerDidAuthor }
              }
            }
          }
        }
        """
        comments: list[dict[str, Any]] = []
        cursor: str | None = None
        node: dict[str, Any] = {}
        while True:
            try:
                data = self.graphql(
                    query, {"o": owner, "n": name, "num": number, "c": cursor}
                )
            except Exception as exc:  # noqa: BLE001
                log(f"Discussion #{number} fetch failed: {exc}")
                return None
            found = ((data.get("data") or {}).get("repository") or {}).get(
                "discussion"
            )
            if not found:
                return None
            node = found
            block = node.get("comments") or {}
            comments.extend(
                c for c in (block.get("nodes") or []) if isinstance(c, dict)
            )
            page_info = block.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return {
            "id": node.get("id"),
            "number": node.get("number"),
            "title": node.get("title") or "",
            "body": node.get("body") or "",
            "url": node.get("url") or "",
            "category": node.get("category") or {},
            "comments": comments,
        }

    # ------------------------------------------------------------------ #
    # Mutating helpers (no-op + log when dry-run)
    # ------------------------------------------------------------------ #
    def _mutate(self, description: str, func) -> Any:
        if self.dry_run:
            summary(f"🟡 [dry-run] would {description}")
            return None
        summary(f"✅ {description}")
        return func()

    def create_comment(self, number: int, body: str) -> Any:
        return self._mutate(
            f"post a comment on #{number}",
            lambda: self._rest(
                "POST",
                f"/repos/{self.repo}/issues/{number}/comments",
                json={"body": body},
            ),
        )

    def update_comment(self, comment_id: int, body: str) -> Any:
        return self._mutate(
            f"update comment {comment_id}",
            lambda: self._rest(
                "PATCH",
                f"/repos/{self.repo}/issues/comments/{comment_id}",
                json={"body": body},
            ),
        )

    def add_labels(self, number: int, labels: list[str]) -> Any:
        if not labels:
            return None
        return self._mutate(
            f"add labels {labels} to #{number}",
            lambda: self._rest(
                "POST",
                f"/repos/{self.repo}/issues/{number}/labels",
                json={"labels": labels},
            ),
        )

    def remove_label(self, number: int, label: str) -> Any:
        def _do() -> Any:
            try:
                return self._rest(
                    "DELETE",
                    f"/repos/{self.repo}/issues/{number}/labels/{label}",
                )
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    return None  # label wasn't present
                raise

        return self._mutate(f"remove label '{label}' from #{number}", _do)

    def add_assignees(self, number: int, assignees: list[str]) -> Any:
        if not assignees:
            return None
        return self._mutate(
            f"assign {assignees} to #{number}",
            lambda: self._rest(
                "POST",
                f"/repos/{self.repo}/issues/{number}/assignees",
                json={"assignees": assignees},
            ),
        )

    def update_issue(self, number: int, **fields: Any) -> Any:
        return self._mutate(
            f"update issue #{number} fields {list(fields)}",
            lambda: self._rest(
                "PATCH", f"/repos/{self.repo}/issues/{number}", json=fields
            ),
        )

    def close_issue(self, number: int, reason: str = "not_planned") -> Any:
        return self._mutate(
            f"close issue #{number} (reason={reason})",
            lambda: self._rest(
                "PATCH",
                f"/repos/{self.repo}/issues/{number}",
                json={"state": "closed", "state_reason": reason},
            ),
        )

    def minimize_comment(self, node_id: str, classifier: str = "OUTDATED") -> Any:
        query = """
        mutation($id: ID!, $classifier: ReportedContentClassifiers!) {
          minimizeComment(input: {subjectId: $id, classifier: $classifier}) {
            minimizedComment { isMinimized }
          }
        }
        """
        return self._mutate(
            f"minimize comment {node_id}",
            lambda: self.graphql(query, {"id": node_id, "classifier": classifier}),
        )

    def add_discussion_comment(self, discussion_id: str, body: str) -> Any:
        query = """
        mutation($d:ID!,$b:String!){
          addDiscussionComment(input:{discussionId:$d, body:$b}){
            comment { id }
          }
        }
        """
        return self._mutate(
            f"post a comment on discussion {discussion_id}",
            lambda: self.graphql(query, {"d": discussion_id, "b": body}),
        )

    def update_discussion_comment(self, comment_id: str, body: str) -> Any:
        query = """
        mutation($id:ID!,$b:String!){
          updateDiscussionComment(input:{commentId:$id, body:$b}){
            comment { id }
          }
        }
        """
        return self._mutate(
            f"update discussion comment {comment_id}",
            lambda: self.graphql(query, {"id": comment_id, "b": body}),
        )

    def commit_files(
        self,
        branch: str,
        files: dict[str, str],
        message: str,
        *,
        repo: str | None = None,
    ) -> Any:
        """Commit text files to ``branch`` via the Git Data API (dry-run aware).

        Creates the branch as a root (orphan) commit if it does not yet exist.
        Used to persist the RAG indexes on the ``triage-index`` branch without
        touching ``main``. Returns the new commit SHA, or ``None`` in dry-run.
        """
        repo = repo or self.repo
        if not files:
            return None

        def _do() -> Any:
            base_sha = self.get_ref_sha(branch, repo=repo)
            base_tree: str | None = None
            parents: list[str] = []
            if base_sha:
                commit = self._rest(
                    "GET", f"/repos/{repo}/git/commits/{base_sha}"
                )
                base_tree = (commit.get("tree") or {}).get("sha")
                parents = [base_sha]
            tree_items = [
                {"path": path, "mode": "100644", "type": "blob", "content": content}
                for path, content in files.items()
            ]
            tree_body: dict[str, Any] = {"tree": tree_items}
            if base_tree:
                tree_body["base_tree"] = base_tree
            new_tree = self._rest("POST", f"/repos/{repo}/git/trees", json=tree_body)
            new_tree_sha = new_tree["sha"]
            commit_obj = self._rest(
                "POST",
                f"/repos/{repo}/git/commits",
                json={"message": message, "tree": new_tree_sha, "parents": parents},
            )
            new_commit_sha = commit_obj["sha"]
            if base_sha:
                self._rest(
                    "PATCH",
                    f"/repos/{repo}/git/refs/heads/{branch}",
                    json={"sha": new_commit_sha, "force": True},
                )
            else:
                self._rest(
                    "POST",
                    f"/repos/{repo}/git/refs",
                    json={"ref": f"refs/heads/{branch}", "sha": new_commit_sha},
                )
            return new_commit_sha

        return self._mutate(
            f"commit {sorted(files)} to {repo}@{branch}", _do
        )
