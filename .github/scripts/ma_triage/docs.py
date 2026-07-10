"""Fetch and chunk the public Music Assistant documentation.

The docs live in the **public** ``music-assistant/music-assistant.io`` repo
(Astro/Starlight), as markdown under ``src/content/docs/**``. Because the repo is
public, the default ``GITHUB_TOKEN`` can read it — no secret is required.

Indexing strategy (mirrors the ``zwave-js-bot`` blueprint):

* enumerate every ``*.md`` / ``*.mdx`` page via the Git Trees API,
* strip YAML frontmatter and MDX ``import``/``export``/JSX noise,
* **chunk by heading**, keeping a breadcrumb path and a stable cite URL per
  chunk (e.g. ``https://www.music-assistant.io/faq/troubleshooting/#networking``),
* oversized sections are split at paragraph boundaries so each chunk stays under
  :data:`config.DOCS_CHUNK_MAX_CHARS`.

This module is deliberately **network-light and pure where possible**:
:func:`chunk_document` takes raw text and does no I/O, so it is trivially
unit-testable; only :func:`doc_paths` / :func:`build_chunks` touch the network.
"""

from __future__ import annotations

import hashlib
import re

from . import config
from .gh import GitHubClient
from .models import DocChunk

_RE_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_RE_FM_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
_RE_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RE_MDX_IMPORT = re.compile(r"^\s*(?:import|export)\s.+$", re.MULTILINE)
_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_JSX_TAG = re.compile(r"</?[A-Za-z][\w.]*(?:\s[^<>]*?)?/?>")
_RE_CODE_FENCE = re.compile(r"^```")
_RE_MULTINEWLINE = re.compile(r"\n{3,}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def slug_for(path: str) -> str:
    """Map a docs repo path to its Starlight slug.

    ``src/content/docs/faq/troubleshooting.md`` -> ``faq/troubleshooting``;
    an ``index`` basename collapses to its parent (``foo/index.md`` -> ``foo``).
    """
    root = config.DOCS_CONTENT_ROOT.strip("/")
    rel = path
    if rel.startswith(root):
        rel = rel[len(root):]
    rel = rel.lstrip("/")
    rel = re.sub(r"\.(md|mdx)$", "", rel, flags=re.IGNORECASE)
    if rel.rsplit("/", 1)[-1].lower() == "index":
        rel = rel.rsplit("/", 1)[0] if "/" in rel else ""
    return rel.lower()


def url_for(slug: str, anchor: str = "") -> str:
    """Build the canonical site URL for a slug (+ optional heading anchor)."""
    base = config.DOCS_SITE.rstrip("/")
    path = f"{base}/{slug}/" if slug else f"{base}/"
    return f"{path}#{anchor}" if anchor else path


def anchor_for(heading: str) -> str:
    """Slugify a heading the way GitHub/Starlight generate anchors."""
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def parse_frontmatter(raw: str) -> tuple[str | None, str]:
    """Return ``(title, body)`` stripping the YAML frontmatter block."""
    match = _RE_FRONTMATTER.match(raw)
    if not match:
        return None, raw
    front = match.group(1)
    title_match = _RE_FM_TITLE.search(front)
    title = None
    if title_match:
        title = title_match.group(1).strip().strip("\"'") or None
    return title, raw[match.end():]


def strip_mdx(body: str) -> str:
    """Remove MDX imports/exports, HTML comments and stray JSX tags."""
    body = _RE_HTML_COMMENT.sub("", body)
    body = _RE_MDX_IMPORT.sub("", body)
    body = _RE_JSX_TAG.sub("", body)
    return body


def _clean_text(text: str) -> str:
    return _RE_MULTINEWLINE.sub("\n\n", text).strip()


def _split_paragraphs(text: str, max_chars: int) -> list[str]:
    """Pack a section body into <= ``max_chars`` pieces at paragraph breaks."""
    text = _clean_text(text)
    if len(text) <= max_chars:
        return [text] if text else []
    pieces: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chars:
            pieces.append(current)
            current = ""
        if len(para) > max_chars:
            # A single very long paragraph: hard-wrap it.
            if current:
                pieces.append(current)
                current = ""
            for i in range(0, len(para), max_chars):
                pieces.append(para[i : i + max_chars])
            continue
        current = f"{current}\n\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def _first_h1(body: str) -> str | None:
    for line in body.splitlines():
        match = _RE_HEADING.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    return None


def chunk_document(path: str, raw: str) -> list[DocChunk]:
    """Split one raw doc into heading-delimited :class:`DocChunk` objects.

    Pure function (no I/O). Embeddings are left empty; the builder fills them in.
    """
    title, body = parse_frontmatter(raw)
    body = strip_mdx(body)
    slug = slug_for(path)
    if not title:
        title = _first_h1(body) or (slug.rsplit("/", 1)[-1] or slug).replace("-", " ").title()

    # Walk the body, accumulating (heading-stack, body-lines) sections.
    sections: list[tuple[list[tuple[int, str]], list[str]]] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []
    in_fence = False

    def _flush() -> None:
        if buffer:
            sections.append((list(stack), list(buffer)))

    for line in body.splitlines():
        if _RE_CODE_FENCE.match(line):
            in_fence = not in_fence
            buffer.append(line)
            continue
        heading = None if in_fence else _RE_HEADING.match(line)
        if heading:
            _flush()
            buffer = []
            level = len(heading.group(1))
            text = heading.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
        else:
            buffer.append(line)
    _flush()

    chunks: list[DocChunk] = []
    seen_ids: set[str] = set()
    for heading_stack, lines in sections:
        text = _clean_text("\n".join(lines))
        if not text:
            continue
        heading = heading_stack[-1][1] if heading_stack else ""
        anchor = anchor_for(heading) if heading else ""
        breadcrumbs = [title] + [h for _, h in heading_stack]
        label = " › ".join([c for c in breadcrumbs if c]) or (title or slug)
        base_id = f"{slug}#{anchor}" if anchor else slug
        for piece in _split_paragraphs(text, config.DOCS_CHUNK_MAX_CHARS):
            chunk_id = base_id
            suffix = 2
            while chunk_id in seen_ids:
                chunk_id = f"{base_id}-{suffix}"
                suffix += 1
            seen_ids.add(chunk_id)
            chunks.append(
                DocChunk(
                    id=chunk_id,
                    path=slug,
                    url=url_for(slug, anchor),
                    title=title,
                    heading=heading,
                    text=piece,
                    breadcrumbs=breadcrumbs,
                    # Hash the breadcrumb label together with the text, because the
                    # embedder sees both — this way a title/breadcrumb-only edit
                    # still invalidates the SHA cache and triggers a re-embed.
                    sha=_sha(f"{label}\n{piece}"),
                )
            )
    return chunks


def doc_paths(gh: GitHubClient) -> list[str]:
    """List every documentation page path in the docs repo."""
    tree = gh.get_tree(config.DOCS_REPO, config.DOCS_REF)
    root = config.DOCS_CONTENT_ROOT.strip("/")
    exclude = config.DOCS_EXCLUDE_PREFIXES
    paths: list[str] = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path") or ""
        if not path.startswith(root):
            continue
        if not re.search(r"\.(md|mdx)$", path, re.IGNORECASE):
            continue
        rel = path[len(root):].lstrip("/")
        if any(rel.startswith(prefix) for prefix in exclude):
            continue
        paths.append(path)
    return sorted(paths)


def build_chunks(
    gh: GitHubClient, paths: list[str] | None = None
) -> list[DocChunk]:
    """Fetch and chunk the whole docs corpus (embeddings still empty)."""
    if paths is None:
        paths = doc_paths(gh)
    chunks: list[DocChunk] = []
    for path in paths:
        raw = gh.get_raw_file(config.DOCS_REPO, path, ref=config.DOCS_REF)
        if not raw:
            continue
        chunks.extend(chunk_document(path, raw))
    return chunks
