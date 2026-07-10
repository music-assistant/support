"""Tests for rendering the RAG sections into the sticky comment."""

from ma_triage import comment, config
from ma_triage.models import (
    DocAnswer,
    DocChunk,
    DocHit,
    RagResult,
    RelatedPost,
    TriageResult,
)


def _chunk(cid="faq/net#mdns"):
    return DocChunk(
        id=cid, path="faq/net", url="https://www.music-assistant.io/faq/net/#mdns",
        title="Networking", heading="mDNS", text="multicast", breadcrumbs=["Networking", "mDNS"],
    )


def test_build_body_high_tier_renders_answer_and_sources():
    rag = RagResult(
        tier="high",
        doc_answer=DocAnswer(True, 0.9, "Enable multicast on your switch.", ["faq/net#mdns"]),
        cited_chunks=[_chunk()],
        related_posts=[RelatedPost("issue", 50, "sonos discovery", "https://x/50", 0.8, "closed")],
    )
    result = TriageResult(form_kind="main", missing_attachment=True, rag=rag)
    body = comment.build_body(result)
    assert config.DOCS_ANSWER_HEADING in body
    assert "Enable multicast on your switch." in body
    assert "https://www.music-assistant.io/faq/net/#mdns" in body
    assert config.RELATED_POSTS_HEADING in body
    assert "#50: sonos discovery" in body
    assert "_(closed)_" in body


def test_build_body_medium_tier_links_only():
    rag = RagResult(tier="medium", doc_hits=[DocHit(_chunk(), 0.4)])
    result = TriageResult(form_kind="main", missing_attachment=True, rag=rag)
    body = comment.build_body(result)
    assert config.DOCS_LINKS_HEADING in body
    assert "https://www.music-assistant.io/faq/net/#mdns" in body
    # No generated prose in a medium (links-only) answer.
    assert config.DOCS_ANSWER_HEADING not in body


def test_build_body_sanitizes_answer():
    rag = RagResult(
        tier="high",
        doc_answer=DocAnswer(True, 0.9, "ping @maintainer and <script>alert(1)</script>", ["faq/net#mdns"]),
        cited_chunks=[_chunk()],
    )
    result = TriageResult(form_kind="main", missing_attachment=True, rag=rag)
    body = comment.build_body(result)
    assert "@maintainer" not in body  # mention neutralised
    assert "<script>" not in body  # HTML escaped


def test_build_body_no_rag_is_unchanged():
    """With rag=None (AI off) the comment carries no RAG sections at all."""
    result = TriageResult(form_kind="main", missing_attachment=True, rag=None)
    body = comment.build_body(result)
    assert config.DOCS_ANSWER_HEADING not in body
    assert config.DOCS_LINKS_HEADING not in body
    assert config.RELATED_POSTS_HEADING not in body


def test_build_body_low_tier_shows_only_related():
    rag = RagResult(
        tier="low",
        related_posts=[RelatedPost("discussion", 12, "similar q", "https://x/12", 0.6, "open")],
    )
    result = TriageResult(form_kind="main", missing_attachment=True, rag=rag)
    body = comment.build_body(result)
    assert config.DOCS_ANSWER_HEADING not in body
    assert config.DOCS_LINKS_HEADING not in body
    assert config.RELATED_POSTS_HEADING in body
    assert "#12: similar q" in body
