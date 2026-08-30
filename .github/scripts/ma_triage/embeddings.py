"""Embeddings client + JSON index read/write.

The client speaks OpenAI-compatible HTTP and takes its endpoint from
``TRIAGE_EMBED_ENDPOINT``, so it does not care what serves it. In CI that is a
process on the runner itself (see ``.github/embeddings``); nothing here assumes
a hosted provider or a credential.

Everything here is **defensive and cost-aware**:

* embeddings are requested in batches, and a failing batch costs only its own
  inputs — the rest are kept, so a long backfill accumulates progress across
  runs instead of discarding it,
* index builds are **cached by content SHA** — an unchanged chunk is never
  re-embedded — and the caller skips the commit entirely when nothing changed,
* a run that cannot embed everything still writes what it has, and reports the
  shortfall; retrieval that ranks on text keeps working from the records while
  ``cmd_index`` fails loudly about the missing vectors,
* ``dim`` records the width the vectors actually have, not the width that was
  requested, because a provider is free to ignore the ``dimensions`` parameter,
* the indexes are plain JSON persisted on the orphan ``triage-index`` branch and
  read back at runtime through :meth:`GitHubClient.get_raw_file`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import requests

from . import config, docs, template
from .gh import GitHubClient, log
from .models import DocChunk
from .retrieval import decode_vec, encode_vec

# Bumped to 2 when embeddings moved from JSON float arrays to base64 int8
# (`retrieval.encode_vec`). An index written by an older schema is discarded and
# rebuilt rather than read: the loaders below treat schema the same way they
# already treat a model or dimension change.
_SCHEMA = 2


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


def embed_texts(texts: list[str], *, token: str) -> list[list[float] | None]:
    """Embed a list of texts, batched. One entry per input, ``None`` where the
    provider did not return a vector.

    A failing batch costs only its own inputs. Collapsing every batch into a
    single ``None`` meant one timed-out request near the end of a long backfill
    discarded thousands of vectors that had already been computed — and because
    a vectorless record is never satisfied by the sha cache, the next run
    retried the whole backlog and could fail the same way indefinitely. Partial
    progress is written instead, so each run advances the cache.
    """
    if not texts:
        return []
    vectors: list[list[float] | None] = []
    batch = max(1, config.EMBED_BATCH)
    for start in range(0, len(texts), batch):
        chunk = texts[start : start + batch]
        try:
            result = _request_embeddings(chunk, token)
        except Exception as exc:  # noqa: BLE001 — never let embeddings break triage
            log(f"Embeddings skipped for {len(chunk)} of {len(texts)}: {exc}")
            vectors.extend([None] * len(chunk))
            continue
        if len(result) != len(chunk):
            log(f"Embeddings response count mismatch for {len(chunk)}; skipping")
            vectors.extend([None] * len(chunk))
            continue
        vectors.extend(result)
    return vectors


def embed_text(text: str, *, token: str) -> list[float] | None:
    """Embed a single text; ``None`` on failure."""
    result = embed_texts([text[: config.MAX_POST_EMBED_CHARS]], token=token)
    return result[0] if result else None


def _chunk_embed_input(chunk: DocChunk) -> str:
    """Text fed to the embedder: breadcrumb label boosts semantic signal."""
    return f"{chunk.label}\n{chunk.text}"[: config.MAX_POST_EMBED_CHARS]


# --------------------------------------------------------------------------- #
# Index (de)serialisation
# --------------------------------------------------------------------------- #
def post_excerpt(body: str | None) -> str:
    """
    The stored excerpt: BM25F's body field, and the assessment's evidence.

    Stripped of the issue form's consent block, which is identical in nearly
    every report and so tells a ranker nothing about which two reports match.
    Every excerpt reaching a comment or the assessment is built here, whether it
    came from the index, the search fallback or a pinned notice.
    The embedded text is *not* stripped: the embedder pools the last token of a
    capped input, so removing text from the top pulls new text past the cap and
    changes the vector wholesale — measured as a recall loss on exactly the
    long reports it applies to.

    Both writers below must produce this identically, or an excerpt that differs
    from the stored one reads as a metadata change and rewrites the index on
    every run.
    """
    return template.strip_boilerplate(str(body or ""))[: config.RELATED_EXCERPT_CHARS]


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


def dim_matches(index: dict[str, Any]) -> bool:
    """Whether an index's stored vector width is usable with the current config.

    ``dim`` records the width the vectors in the file actually have, not the
    width that was requested. When ``EMBED_DIM`` asks for a specific width the
    file has to match it; when it asks for nothing (0), whatever the provider
    natively returned is fine. Recording the request instead would let a
    provider that ignores the ``dimensions`` parameter produce a header that
    does not describe the file — and `cosine` scores mismatched widths as 0.0,
    so that disagreement would surface as duplicate detection quietly finding
    nothing rather than as an error.
    """
    stored = index.get("dim")
    if config.EMBED_DIM > 0:
        return stored == config.EMBED_DIM
    return isinstance(stored, int) and stored > 0


def load_docs_chunks(gh: GitHubClient) -> list[DocChunk]:
    """Load ``docs.json`` into :class:`DocChunk` objects (with embeddings)."""
    index = load_index(gh, config.DOCS_INDEX_PATH)
    if not index:
        return []
    if (
        index.get("schema") != _SCHEMA
        or index.get("model") != config.EMBED_MODEL
        or not dim_matches(index)
    ):
        log("Docs index schema/model/dim mismatch; ignoring index")
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
                embedding=decode_vec(raw.get("embedding")),
            )
        )
    return chunks


def load_posts(gh: GitHubClient) -> list[dict[str, Any]]:
    """Load ``posts.json`` records (each with an ``embedding``)."""
    index = load_index(gh, config.POSTS_INDEX_PATH)
    if not index:
        return []
    if (
        index.get("schema") != _SCHEMA
        or index.get("model") != config.EMBED_MODEL
        or not dim_matches(index)
    ):
        log("Posts index schema/model/dim mismatch; ignoring index")
        return []
    posts = index.get("posts")
    return [p for p in posts if isinstance(p, dict) and p.get("embedding")] if isinstance(posts, list) else []


# Schema versions whose *text* layout this code understands. `_SCHEMA` tracks
# how a vector is encoded (2 = base64 int8), which is irrelevant to a reader
# that never looks at one — but it is enumerated rather than ignored, so a
# future layout change to the record itself still has to be considered here
# instead of being silently accepted.
_TEXT_COMPATIBLE_SCHEMAS = (1, 2)


def load_posts_text(gh: GitHubClient) -> list[dict[str, Any]]:
    """Load ``posts.json`` records for retrieval that ranks on text alone.

    Unlike :func:`load_posts` this ignores ``model`` and ``dim``: those guard
    vector compatibility, and a reader that scores tokens does not care which
    embedder produced a file it will not read vectors from. It also keeps
    records that have no vector at all, which is the whole point — those are
    the posts indexed while the provider was unavailable.

    ``embedding`` is stripped from every record returned. A schema-1 record
    holds a raw float list rather than base64, and :func:`retrieval.decode_vec`
    raises on that by design; letting one through would put a hard failure
    inside the path that exists to survive failure.

    Schema-1 records may predate ``excerpt``. Those still rank, on their title
    alone — worse, but not a failure.
    """
    index = load_index(gh, config.POSTS_INDEX_PATH)
    if not index:
        return []
    if index.get("schema") not in _TEXT_COMPATIBLE_SCHEMAS:
        log(
            f"Posts index schema {index.get('schema')} has no known text layout; "
            "ignoring index"
        )
        return []
    posts = index.get("posts")
    if not isinstance(posts, list):
        return []
    return [
        {key: value for key, value in post.items() if key != "embedding"}
        for post in posts
        if isinstance(post, dict)
    ]


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
        "embedding": encode_vec(chunk.embedding),
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
        and previous.get("schema") == _SCHEMA
        and previous.get("model") == config.EMBED_MODEL
        and dim_matches(previous)
    ):
        for raw in previous.get("chunks", []) or []:
            if isinstance(raw, dict) and raw.get("id"):
                prev_by_id[raw["id"]] = raw

    to_embed: list[int] = []
    for i, chunk in enumerate(chunks):
        cached = prev_by_id.get(chunk.id)
        if cached and cached.get("sha") == chunk.sha and cached.get("embedding"):
            chunk.embedding = decode_vec(cached["embedding"])
        else:
            to_embed.append(i)

    if to_embed:
        vectors = embed_texts(
            [_chunk_embed_input(chunks[i]) for i in to_embed], token=token
        )
        if not any(vector is not None for vector in vectors):
            return None, False
        for i, vector in zip(to_embed, vectors):
            if vector is not None:
                chunks[i].embedding = vector

    new_ids = {c.id for c in chunks}
    changed = bool(to_embed) or new_ids != set(prev_by_id)

    index = {
        "schema": _SCHEMA,
        "model": config.EMBED_MODEL,
        "dim": next((len(c.embedding) for c in chunks if c.embedding), 0),
        "built_at": _now_iso(),
        "chunks": [_chunk_to_dict(c) for c in chunks],
    }
    return index, changed


def reusable_vector(cached: dict[str, Any] | None, sha: str) -> bool:
    """Whether ``cached`` already holds a vector computed from this exact text.

    The sha check is what keeps a vector paired with the text it was computed
    from; an edited post fails it and must be re-embedded before its vector can
    be trusted again.
    """
    return bool(cached and cached.get("sha") == sha and cached.get("embedding"))


def _post_record(
    post: dict[str, Any], embedding: list[float] | None
) -> dict[str, Any]:
    """One index record. ``embedding`` is ``None`` when the provider was down.

    The key is then omitted rather than written empty: ``encode_vec([])`` also
    produces ``""``, so an empty string would merge "the encoder produced
    nothing" with "we never asked". Readers filter on the key's presence, so an
    absent vector removes the record from dense retrieval and leaves it
    available to everything that only needs its text.
    """
    record = {
        "kind": post.get("kind", "issue"),
        "number": int(post.get("number", 0)),
        "title": str(post.get("title", "")),
        "url": str(post.get("url", "")),
        "state": post.get("state"),
        "updated_at": post.get("updated_at"),
        "providers": sorted(
            {
                str(provider)
                for provider in (post.get("providers") or [])
                if str(provider).strip()
            },
            key=str.lower,
        ),
        "excerpt": post_excerpt(post.get("body")),
        "sha": post_sha(str(post.get("title", "")), str(post.get("body", ""))),
    }
    if embedding:
        record["embedding"] = encode_vec(embedding)
    return record


def trim_by_kind(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Keep the newest records per kind, up to each kind's own cap.

    Trimming the combined list by a single cap lets whichever kind is busier
    evict the other; issues and discussions are retained independently so
    duplicate detection's issue history does not depend on discussion volume.
    Input order is preserved, so callers control what "newest" means.
    """
    caps = {
        "issue": config.INDEX_MAX_ISSUES,
        "discussion": config.INDEX_MAX_DISCUSSIONS,
    }
    seen: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    for record in records:
        kind = str(record.get("kind", "issue"))
        cap = caps.get(kind, config.INDEX_MAX_ISSUES)
        if seen.get(kind, 0) >= cap:
            continue
        seen[kind] = seen.get(kind, 0) + 1
        kept.append(record)
    return kept


def _observed_dim(records: list[dict[str, Any]]) -> int:
    """Width of the vectors actually stored, or 0 when none are."""
    for record in records:
        raw = record.get("embedding")
        if raw:
            return len(decode_vec(raw))
    return 0


def _empty_posts_index() -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "model": config.EMBED_MODEL,
        "dim": 0,  # replaced with the observed width once vectors exist
        "built_at": _now_iso(),
        "posts": [],
    }


def build_posts_index(
    gh: GitHubClient,
    posts: list[dict[str, Any]],
    *,
    token: str,
    previous: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Build the posts index from ``{kind,number,title,body,url,state,...}`` dicts.

    Always returns an index. A provider outage costs individual records their
    vectors, not the whole build — ``index["vectors"]`` reports how many
    records carry one, which is what tells the caller the run fell short.
    """
    prev_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    if (
        previous
        and previous.get("schema") == _SCHEMA
        and previous.get("model") == config.EMBED_MODEL
        and dim_matches(previous)
    ):
        for raw in previous.get("posts", []) or []:
            if isinstance(raw, dict) and raw.get("number") is not None:
                prev_by_key[(raw.get("kind", "issue"), int(raw["number"]))] = raw

    records: list[dict[str, Any]] = []
    to_embed: list[dict[str, Any]] = []
    embed_targets: list[str] = []
    metadata_changed = False
    for post in trim_by_kind(posts):
        key = (post.get("kind", "issue"), int(post.get("number", 0)))
        sha = post_sha(str(post.get("title", "")), str(post.get("body", "")))
        cached = prev_by_key.get(key)
        if reusable_vector(cached, sha):
            record = dict(cached)
            providers = sorted(
                {
                    str(provider)
                    for provider in (post.get("providers") or [])
                    if str(provider).strip()
                },
                key=str.lower,
            )
            excerpt = post_excerpt(post.get("body"))
            if record.get("providers") != providers:
                record["providers"] = providers
                metadata_changed = True
            if record.get("excerpt") != excerpt:
                record["excerpt"] = excerpt
                metadata_changed = True
            records.append(record)
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
        # A dead provider costs this run its *new* vectors, not the index. Every
        # post whose text is unchanged keeps the vector cached above, and the
        # rest are still written with their text so retrieval that needs no
        # vector keeps working. `cmd_index` reports the shortfall and still
        # exits non-zero; leaving no index at all is what left duplicate
        # detection with nothing to fall back on.
        vectors = embed_texts(embed_targets, token=token)
        for i, post in enumerate(to_embed):
            records.append(_post_record(post, vectors[i] if i < len(vectors) else None))

    changed = bool(to_embed) or metadata_changed or {
        (r.get("kind", "issue"), int(r.get("number", 0))) for r in records
    } != set(prev_by_key)

    records.sort(key=lambda r: int(r.get("number", 0)), reverse=True)
    if changed and previous and previous.get("posts") == records:
        # A post with no vector is never satisfied by the cache, so `to_embed`
        # stays non-empty for every night of an outage. Without this the build
        # would commit an index identical to yesterday's but for its timestamp,
        # once a night, for as long as the provider stays down.
        changed = False

    index = _empty_posts_index()
    index["posts"] = records
    index["vectors"] = sum(1 for r in records if r.get("embedding"))
    index["dim"] = _observed_dim(records)
    return index, changed


def append_post(
    gh: GitHubClient, post: dict[str, Any], *, token: str
) -> tuple[dict[str, Any], bool]:
    """Embed a single new post and upsert it into the posts index.

    Returns the index and whether the upserted record carries a vector, so the
    caller can report a provider outage without having to inspect the record.

    Between nightly builds this is the only path that admits new posts, so it
    writes the record whether or not a vector could be obtained. Unlike the
    nightly build there is no cache to fall back on here, so an existing vector
    for unchanged text is kept rather than overwritten with a vectorless
    record — a post edited during a provider outage would otherwise lose a good
    vector it could not get back until the next successful build.
    """
    previous = load_index(gh, config.POSTS_INDEX_PATH) or _empty_posts_index()
    vector = embed_text(
        f"{post.get('title', '')}\n\n{post.get('body', '')}", token=token
    )
    previous_posts = [
        p for p in previous.get("posts", []) or [] if isinstance(p, dict)
    ]
    record = _post_record(post, vector)
    key = (record["kind"], record["number"])
    if vector is None:
        cached = next(
            (
                p
                for p in previous_posts
                if (p.get("kind", "issue"), int(p.get("number", 0))) == key
            ),
            None,
        )
        if reusable_vector(cached, record["sha"]):
            record["embedding"] = cached["embedding"]

    kept = [
        p
        for p in previous_posts
        if (p.get("kind", "issue"), int(p.get("number", 0))) != key
    ]
    kept.append(record)
    kept.sort(key=lambda r: int(r.get("number", 0)), reverse=True)
    kept = trim_by_kind(kept)
    index = _empty_posts_index()
    index["posts"] = kept
    index["vectors"] = sum(1 for r in kept if r.get("embedding"))
    index["dim"] = _observed_dim(kept)
    return index, bool(record.get("embedding"))


def save_index(
    gh: GitHubClient, path: str, index: dict[str, Any], *, message: str
) -> Any:
    """Persist a JSON index to the orphan index branch (dry-run aware)."""
    return gh.commit_files(config.INDEX_BRANCH, {path: _dumps(index)}, message)
