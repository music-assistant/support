from ma_triage import config
from ma_triage.sanitize import fenced, inline, link_label, markdown_safe


def test_inline_neutralizes_mentions():
    out = inline("hello @team and @user")
    assert "@team" not in out  # a zero-width space is inserted after @
    assert "\u200b" in out


def test_inline_neutralizes_issue_refs():
    out = inline("see #123")
    assert "#\u200b123" in out


def test_inline_escapes_html():
    out = inline("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_inline_replaces_backticks():
    assert "`" not in inline("a `code` b")


def test_inline_collapses_whitespace():
    assert inline("a\n\n  b\tc") == "a b c"


def test_inline_truncates():
    out = inline("A" * 1000, max_len=100)
    assert "truncated" in out
    assert len(out) < 200


def test_inline_empty():
    assert inline(None) == ""
    assert inline("") == ""


def test_fenced_strips_backticks_and_keeps_newlines():
    out = fenced("line1\n```\nline2")
    assert "`" not in out
    assert "\n" in out


def test_fenced_defuses_state_marker():
    out = fenced("<!-- ma-triage-state:{\"x\":1} -->")
    assert "<!--" not in out
    assert "&lt;!--" in out


def test_link_label_escapes_brackets_and_preceding_backslashes():
    out = link_label(r"pwn\](https://evil.example)")
    assert out.startswith(r"pwn\\\]")
    assert "\u200b" not in out


def test_markdown_safe_defangs_links_images_and_bare_urls():
    out = markdown_safe(
        "[click](https://evil.example) ![x](http://evil.example) "
        "https://evil.example mailto:bad@example.com www.evil.example"
    )
    assert r"\[click\]" in out
    assert r"!\[x\]" in out
    assert "https://evil.example" not in out
    assert "http://evil.example" not in out
    assert "mailto:bad@example.com" not in out
    assert "www.evil.example" not in out
    assert "https:\u200b//evil.example" in out
