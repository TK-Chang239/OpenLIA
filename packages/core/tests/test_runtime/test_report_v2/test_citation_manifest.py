"""Tests for citation_manifest module (Task O2)."""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.rendering.citation_manifest import (
    assemble_citation_manifest,
    render_sources_footer,
    substitute_markers,
)
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation


def cite(id: str, title: str = "t") -> Citation:
    return Citation(
        id=id,
        source_type="tool_call",
        tool="eodhd.x",
        url=None,
        title=title,
        retrieved_at=datetime(2026, 5, 1, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# assemble_citation_manifest
# ---------------------------------------------------------------------------


def test_assemble_orders_by_first_appearance_and_dedupes() -> None:
    pool = {"c1": cite("c1"), "c2": cite("c2"), "c3": cite("c3")}
    texts = ["[c:c2] [c:c1]", "[c:c1]", "[c:c3]"]
    manifest = assemble_citation_manifest(pool, texts)

    assert manifest.id_to_number == {"c2": 1, "c1": 2, "c3": 3}
    assert len(manifest.citations) == 3
    assert manifest.citations[0].id == "c2"
    assert manifest.citations[1].id == "c1"
    assert manifest.citations[2].id == "c3"


def test_backlink_count_tracks_multiple_references() -> None:
    pool = {"c1": cite("c1")}
    texts = ["[c:c1] [c:c1] [c:c1]"]
    manifest = assemble_citation_manifest(pool, texts)

    assert manifest.backlink_counts["c1"] == 3


# ---------------------------------------------------------------------------
# substitute_markers
# ---------------------------------------------------------------------------


def test_substitute_markers_replaces_with_sup_anchors() -> None:
    pool = {"c1": cite("c1")}
    manifest = assemble_citation_manifest(pool, ["[c:c1]"])
    result = substitute_markers("claim [c:c1].", manifest)

    assert "[1]" in result
    assert "cite-1" in result
    assert "<sup>" in result


def test_substitute_leaves_unresolved_markers_unchanged() -> None:
    manifest = assemble_citation_manifest({}, [""])
    result = substitute_markers("text [c:unknown] end", manifest)

    assert "[c:unknown]" in result


# ---------------------------------------------------------------------------
# render_sources_footer
# ---------------------------------------------------------------------------


def test_render_sources_footer_empty_returns_empty_string() -> None:
    manifest = assemble_citation_manifest({}, [])
    assert render_sources_footer(manifest) == ""


def test_render_sources_footer_emits_ol_with_backlinks() -> None:
    pool = {"c1": cite("c1", title="Source A")}
    # Reference c1 twice so backlink_counts["c1"] == 2
    texts = ["[c:c1]", "[c:c1]"]
    manifest = assemble_citation_manifest(pool, texts)
    footer = render_sources_footer(manifest)

    assert "<ol" in footer
    assert "Source A" in footer
    assert footer.count("cite-backlink") == 2


def test_html_escape_applied_to_titles_for_xss() -> None:
    pool = {"c1": cite("c1", title="<script>alert(1)</script>")}
    texts = ["[c:c1]"]
    manifest = assemble_citation_manifest(pool, texts)
    footer = render_sources_footer(manifest)

    assert "<script>" not in footer
    assert "&lt;script&gt;" in footer
