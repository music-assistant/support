"""GitHub Models embeddings client + JSON index read/write.

The embeddings API is OpenAI-compatible and served from ``models.github.ai`` with
the default ``GITHUB_TOKEN`` (``models: read`` permission) — no secret required.

Everything here is **defensive and cost-aware**:

* embeddings are requested in batches, with a reduced ``dimensions`` to keep the
  indexes small; any HTTP / network failure returns ``None`` (**skip-on-limit**)
  so a rate-limited run never writes a broken index,
* index builds are **cached by content SHA** — an unchanged chunk is never
  re-embedded — and the caller skips the commit entirely when nothing changed,
* the indexes are plain JSON persisted on the orphan ``triage-index`` branch and
  read back at runtime through :meth:`GitHubClient.get_raw_file`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import requests

from . import config, docs
from .gh import GitHubClient, log
from .models import DocChunk

_SCHEMA = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def post_sha(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Embeddings client
# --------------------------------------------------------------------------- #
def _request_embeddings(inputs: list[str], token: str) -> list[list[float]]:
    """One embeddings API call for a batch of inputs (raises on any error)."""
    payload: dict[str, Any] = {"model": config.EMBED_MODEL, "input": inputs}
    if config.EMBED_DIM > 0:
        payload["dimensions"] = config.EMBED_DIM
    resp = requests.post(
        config.EMBED_ENDPOINT, headers=_headers(token), json=payload, timeout=60
    )
    if resp.status_code >= 400:
        raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()["data"]
    # The API preserves input order, but sort by index to be safe.
    ordered = sorted(data, key=lambda d: d.get("index", 0))
    return [list(item["embedding"]) for item in ordered]


def embed_texts(texts: list[str], *, token: str) -> list[list[float]] | None:
    """Embed a list of texts (batched). Returns ``None`` on any failure."""
    if not texts:
        return []
    vectors: list[list[float]] = []
    batch = max(1, config.EMBED_BATCH)
    try:
        for start in range(0, len(texts), batch):
            chunk = texts[start : start + batch]
            vectors.extend(_request_embeddings(chunk, token))
    except Exception as exc:  # noqa: BLE001 — never let embeddings break triage
        log(f"Embeddings skipped: {exc}")
        return None
    if len(vectors) != len(texts):
        log("Embeddings response count mismatch; skipping")
        return None
    return vectors


def embed_text(text: str, *, token: str) -> list[float] | None:
    """Embed a single text; ``None`` on failure."""
    result = embed_texts([text[: config.MAX_POST_EMBED_CHARS]], token=token)
    if not result:
        return None
    return result[0]


def _chunk_embed_input(chunk: DocChunk) -> str:
    """Text fed to the embedder: breadcrumb label boosts semantic signal."""
    return f"{chunk.label}\n{chunk.text}"[: config.MAX_POST_EMBED_CHARS]


# --------------------------------------------------------------------------- #
# Index (de)serialisation
# --------------------------------------------------------------------------- #
def _dumps(index: dict[str, Any]) -> str:
    return json.dumps(index, separators=(",", ":"), sort_keys=True)


def load_index(gh: GitHubClient, path: str) -> dict[str, Any] | None:
    """Read + parse a JSON index from the index branch; ``None`` if absent/bad."""
    raw = gh.get_raw_file(gh.repo, path, ref=config.INDEX_BRANCH)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log(f"Index {path} is not valid JSON: {exc}")
        return None
    return data if isinstance(data, dict) else None


def load_docs_chunks(gh: GitHubClient) -> list[DocChunk]:
    """Load ``docs.json`` into :class:`DocChunk` objects (with embeddings)."""
    index = load_index(gh, config.DOCS_INDEX_PATH)
    if not index:
        return []
    if index.get("model") != config.EMBED_MODEL or index.get("dim") != config.EMBED_DIM:
        log("Docs index model/dim mismatch; ignoring index")
        return []
    chunks: list[DocChunk] = []
    for raw in index.get("chunks", []) or []:
        if not isinstance(raw, dict) or not raw.get("embedding"):
            continue
        chunks.append(
            DocChunk(
                id=str(raw.get("id", "")),
                path=str(raw.get("path", "")),
                url=str(raw.get("url", "")),
                title=str(raw.get("title", "")),
                heading=str(raw.get("heading", "")),
                text=str(raw.get("text", "")),
                breadcrumbs=list(raw.get("breadcrumbs", []) or []),
                sha=str(raw.get("sha", "")),
                embedding=[float(x) for x in raw.get("embedding", [])],
            )
        )
    return chunks


def load_posts(gh: GitHubClient) -> list[dict[str, Any]]:
    """Load ``posts.json`` records (each with an ``embedding``)."""
    index = load_index(gh, config.POSTS_INDEX_PATH)
    if not index:
        return []
    if index.get("model") != config.EMBED_MODEL or index.get("dim") != config.EMBED_DIM:
        return []
    posts = index.get("posts")
    return [p for p in posts if isinstance(p, dict) and p.get("embedding")] if isinstance(posts, list) else []


def load_suppress(gh: GitHubClient) -> list[dict[str, Any]]:
    """Load the downvoted-answer fingerprints from ``suppress.json``."""
    index = load_index(gh, config.SUPPRESS_INDEX_PATH)
    if not index:
        return []
    fps = index.get("fingerprints")
    return [f for f in fps if isinstance(f, dict)] if isinstance(fps, list) else []


def _chunk_to_dict(chunk: DocChunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "path": chunk.path,
        "url": chunk.url,
        "title": chunk.title,
        "heading": chunk.heading,
        "text": chunk.text,
        "breadcrumbs": chunk.breadcrumbs,
        "sha": chunk.sha,
        "embedding": chunk.embedding,
    }


# --------------------------------------------------------------------------- #
# Index builders (used by the `index` subcommand)
# --------------------------------------------------------------------------- #
def build_docs_index(
    gh: GitHubClient,
    *,
    token: str,
    chunks: list[DocChunk] | None = None,
    previous: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    """Build the docs index, reusing cached embeddings by content SHA.

    Returns ``(index, changed)``. ``index`` is ``None`` when embedding failed
    (rate limit / network) so the caller keeps the previous index untouched.
    ``changed`` is ``False`` when the corpus is byte-for-byte identical to
    ``previous`` (nothing to re-embed, no added/removed chunks) — the caller then
    skips the commit.
    """
    if chunks is None:
        chunks = docs.build_chunks(gh)

    prev_by_id: dict[str, dict[str, Any]] = {}
    if (
        previous
        and previous.get("model") == config.EMBED_MODEL
        and previous.get("dim") == config.EMBED_DIM
    ):
        for raw in previous.get("chunks", []) or []:
            if isinstance(raw, dict) and raw.get("id"):
                prev_by_id[raw["id"]] = raw

    to_embed: list[int] = []
    for i, chunk in enumerate(chunks):
        cached = prev_by_id.get(chunk.id)
        if cached and cached.get("sha") == chunk.sha and cached.get("embedding"):
            chunk.embedding = [float(x) for x in cached["embedding"]]
        else:
            to_embed.append(i)

    if to_embed:
        vectors = embed_texts(
            [_chunk_embed_input(chunks[i]) for i in to_embed], token=token
        )
        if vectors is None:
            return None, False
        for i, vector in zip(to_embed, vectors):
            chunks[i].embedding = vector

    new_ids = {c.id for c in chunks}
    changed = bool(to_embed) or new_ids != set(prev_by_id)

    index = {
        "schema": _SCHEMA,
        "model": config.EMBED_MODEL,
        "dim": config.EMBED_DIM,
        "built_at": _now_iso(),
        "chunks": [_chunk_to_dict(c) for c in chunks],
    }
    return index, changed


def _post_record(post: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    return {
        "kind": post.get("kind", "issue"),
        "number": int(post.get("number", 0)),
        "title": str(post.get("title", "")),
        "url": str(post.get("url", "")),
        "state": post.get("state"),
        "updated_at": post.get("updated_at"),
        "sha": post_sha(str(post.get("title", "")), str(post.get("body", ""))),
        "embedding": embedding,
    }


def _empty_posts_index() -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "model": config.EMBED_MODEL,
        "dim": config.EMBED_DIM,
        "built_at": _now_iso(),
        "posts": [],
    }


def build_posts_index(
    gh: GitHubClient,
    posts: list[dict[str, Any]],
    *,
    token: str,
    previous: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    """Build the posts index from ``{kind,number,title,body,url,state,...}`` dicts."""
    prev_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    if (
        previous
        and previous.get("model") == config.EMBED_MODEL
        and previous.get("dim") == config.EMBED_DIM
    ):
        for raw in previous.get("posts", []) or []:
            if isinstance(raw, dict) and raw.get("number") is not None:
                prev_by_key[(raw.get("kind", "issue"), int(raw["number"]))] = raw

    records: list[dict[str, Any]] = []
    to_embed: list[dict[str, Any]] = []
    embed_targets: list[str] = []
    for post in posts[: config.INDEX_MAX_POSTS]:
        key = (post.get("kind", "issue"), int(post.get("number", 0)))
        sha = post_sha(str(post.get("title", "")), str(post.get("body", "")))
        cached = prev_by_key.get(key)
        if cached and cached.get("sha") == sha and cached.get("embedding"):
            records.append(cached)
        else:
            to_embed.append(post)
            # Cap each target so a very long issue/discussion body can't exceed
            # the embedding model's token limit and fail the whole batch.
            embed_targets.append(
                f"{post.get('title', '')}\n\n{post.get('body', '')}"[
                    : config.MAX_POST_EMBED_CHARS
                ]
            )

    if to_embed:
        vectors = embed_texts(embed_targets, token=token)
        if vectors is None:
            return None, False
        for post, vector in zip(to_embed, vectors):
            records.append(_post_record(post, vector))

    changed = bool(to_embed) or {
        (r.get("kind", "issue"), int(r.get("number", 0))) for r in records
    } != set(prev_by_key)

    records.sort(key=lambda r: int(r.get("number", 0)), reverse=True)
    index = _empty_posts_index()
    index["posts"] = records
    return index, changed


def append_post(
    gh: GitHubClient, post: dict[str, Any], *, token: str
) -> tuple[dict[str, Any] | None, bool]:
    """Embed a single new post and upsert it into the posts index."""
    previous = load_index(gh, config.POSTS_INDEX_PATH) or _empty_posts_index()
    vector = embed_text(
        f"{post.get('title', '')}\n\n{post.get('body', '')}", token=token
    )
    if vector is None:
        return None, False
    record = _post_record(post, vector)
    key = (record["kind"], record["number"])
    kept = [
        p
        for p in previous.get("posts", []) or []
        if isinstance(p, dict)
        and (p.get("kind", "issue"), int(p.get("number", 0))) != key
    ]
    kept.append(record)
    kept.sort(key=lambda r: int(r.get("number", 0)), reverse=True)
    kept = kept[: config.INDEX_MAX_POSTS]
    index = _empty_posts_index()
    index["posts"] = kept
    return index, True


def save_index(
    gh: GitHubClient, path: str, index: dict[str, Any], *, message: str
) -> Any:
    """Persist a JSON index to the orphan index branch (dry-run aware)."""
    return gh.commit_files(config.INDEX_BRANCH, {path: _dumps(index)}, message)
