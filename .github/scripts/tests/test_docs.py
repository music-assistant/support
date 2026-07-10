"""Tests for docs fetching / heading-based chunking (pure, offline)."""

from ma_triage import config, docs


def test_slug_for_variants():
    assert docs.slug_for("src/content/docs/faq/troubleshooting.md") == "faq/troubleshooting"
    assert docs.slug_for("src/content/docs/index.md") == ""
    assert docs.slug_for("src/content/docs/settings/core.mdx") == "settings/core"
    assert docs.slug_for("src/content/docs/player-support/index.md") == "player-support"


def test_url_and_anchor():
    assert docs.url_for("faq/troubleshooting") == "https://www.music-assistant.io/faq/troubleshooting/"
    assert docs.url_for("") == "https://www.music-assistant.io/"
    assert (
        docs.url_for("faq/troubleshooting", "my-heading")
        == "https://www.music-assistant.io/faq/troubleshooting/#my-heading"
    )
    assert docs.anchor_for("Networking & mDNS!") == "networking-mdns"


def test_parse_frontmatter():
    title, body = docs.parse_frontmatter("---\ntitle: Hello World\ndescription: x\n---\n\n# H1\ntext")
    assert title == "Hello World"
    assert body.strip().startswith("# H1")


def test_strip_mdx_removes_imports_and_jsx():
    body = "import Foo from 'bar';\n\n<Card>hi</Card>\n<!-- secret -->\ntext"
    out = docs.strip_mdx(body)
    assert "import Foo" not in out
    assert "<Card>" not in out
    assert "secret" not in out
    assert "text" in out


def test_chunk_document_by_heading():
    raw = (
        "---\ntitle: Troubleshooting\n---\n\n"
        "# First steps\n\nLook in the logs.\n\n"
        "## Networking\n\nRunning behind VPNs is not supported.\n\n"
        "### mDNS\n\nPlayers are discovered using mDNS.\n"
    )
    chunks = docs.chunk_document("src/content/docs/faq/troubleshooting.md", raw)
    ids = [c.id for c in chunks]
    assert ids == [
        "faq/troubleshooting#first-steps",
        "faq/troubleshooting#networking",
        "faq/troubleshooting#mdns",
    ]
    networking = next(c for c in chunks if c.heading == "Networking")
    assert networking.breadcrumbs == ["Troubleshooting", "First steps", "Networking"]
    assert networking.url == "https://www.music-assistant.io/faq/troubleshooting/#networking"
    assert all(c.sha for c in chunks)  # every chunk has a content SHA


def test_chunk_document_intro_before_first_heading():
    raw = "---\ntitle: Intro Page\n---\n\nSome intro text with no heading yet.\n\n# Later\n\nmore\n"
    chunks = docs.chunk_document("src/content/docs/intro.md", raw)
    assert chunks[0].id == "intro"
    assert chunks[0].heading == ""
    assert chunks[0].breadcrumbs == ["Intro Page"]


def test_chunk_document_splits_long_sections(monkeypatch):
    monkeypatch.setattr(config, "DOCS_CHUNK_MAX_CHARS", 40)
    para = "word " * 20  # ~100 chars
    raw = f"---\ntitle: Big\n---\n\n# Section\n\n{para}\n\n{para}\n"
    chunks = docs.chunk_document("src/content/docs/big.md", raw)
    assert len(chunks) >= 2
    assert all(len(c.text) <= 40 for c in chunks)
    # Split pieces get suffixed, unique ids.
    assert len(set(c.id for c in chunks)) == len(chunks)


def test_chunk_document_ignores_headings_in_code_fences():
    raw = (
        "---\ntitle: Code\n---\n\n"
        "# Real heading\n\n```\n# not a heading\nsome code\n```\n\nmore text\n"
    )
    chunks = docs.chunk_document("src/content/docs/code.md", raw)
    assert len(chunks) == 1
    assert chunks[0].heading == "Real heading"
    assert "not a heading" in chunks[0].text


def test_chunk_sha_changes_when_title_changes():
    body = "# Section\n\nidentical body text\n"
    old = docs.chunk_document("src/content/docs/p.md", "---\ntitle: Old\n---\n\n" + body)
    new = docs.chunk_document("src/content/docs/p.md", "---\ntitle: New\n---\n\n" + body)
    # Body text is identical, but the breadcrumb label changed with the title, so
    # the SHA (used as the embed cache key) must differ to force a re-embed.
    assert old[0].text == new[0].text
    assert old[0].sha != new[0].sha


def test_doc_paths_filters_and_excludes(fake_gh, monkeypatch):
    monkeypatch.setattr(
        fake_gh,
        "_tree",
        [
            {"path": "src/content/docs/faq/troubleshooting.md", "type": "blob"},
            {"path": "src/content/docs/settings/core.mdx", "type": "blob"},
            {"path": "src/content/docs/blog/2024/post.md", "type": "blob"},
            {"path": "src/content/docs/assets/logo.png", "type": "blob"},
            {"path": "src/content/docs/faq", "type": "tree"},
            {"path": "README.md", "type": "blob"},
        ],
        raising=False,
    )
    paths = docs.doc_paths(fake_gh)
    assert "src/content/docs/faq/troubleshooting.md" in paths
    assert "src/content/docs/settings/core.mdx" in paths
    assert not any("blog/" in p for p in paths)  # blog excluded by default
    assert not any(p.endswith(".png") for p in paths)
    assert "README.md" not in paths
