from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.rendering.block_renderer import render_block


def test_prose_block_renders_markdown_to_html():
    out = render_block({"type": "prose", "text": "Q3 **revenue** grew 18% [c:c1]."})
    assert "<strong>revenue</strong>" in out or "<b>revenue</b>" in out
    assert "[c:c1]" in out  # citation markers preserved for later pass


def test_table_block_renders_html_table():
    out = render_block(
        {
            "type": "table",
            "headers": ["Metric", "Value"],
            "rows": [["Revenue", "$94.9B"], ["EPS", "$2.40"]],
            "caption": "Q3 results",
        }
    )
    assert "<table" in out
    assert "<th>Metric</th>" in out
    assert "<td>$94.9B</td>" in out
    assert "Q3 results" in out


def test_kpi_strip_renders_cells():
    out = render_block(
        {
            "type": "kpi_strip",
            "cells": [{"label": "Revenue", "value": "$94.9B", "unit": "USD", "delta": "+18%"}],
        }
    )
    assert "kpi-strip" in out
    assert "$94.9B" in out
    assert "+18%" in out


def test_skip_banner_renders_blockquote():
    out = render_block(
        {
            "type": "skip_banner",
            "section_name": "Litigation Risk",
            "reason": "no material cases",
        }
    )
    assert "skip-banner" in out
    assert "Litigation Risk" in out


def test_degraded_banner_renders_blockquote():
    out = render_block(
        {
            "type": "degraded_banner",
            "section_name": "Litigation Risk",
            "reason": "sparse data",
            "issue_list": ["content_too_sparse"],
        }
    )
    assert "degraded-banner" in out


def test_chart_svg_inline_renders_inline_svg():
    payload = "<svg><circle r='5'/></svg>"
    out = render_block({"type": "chart", "format": "svg_inline", "payload": payload})
    assert payload in out


def test_chart_png_renders_data_url_img():
    out = render_block({"type": "chart", "format": "png_base64", "payload": "aGVsbG8="})
    assert "data:image/png;base64,aGVsbG8=" in out


def test_quote_block_renders_with_citation():
    out = render_block(
        {
            "type": "quote_block",
            "quote": "Revenue beat expectations.",
            "source": "CFO earnings call",
            "citation_id": "c1",
        }
    )
    assert "Revenue beat expectations." in out
    assert "[c:c1]" in out


def test_excel_attachment_renders_download_link():
    out = render_block(
        {
            "type": "excel_attachment",
            "filename": "financials.xlsx",
            "download_url": "/downloads/financials.xlsx",
            "row_count": 42,
            "sheet_count": 3,
        }
    )
    assert '<a class="attachment"' in out
    assert "financials.xlsx" in out


def test_unknown_block_type_renders_visible_placeholder():
    # Unknown block types now degrade to a visible placeholder rather than
    # aborting Stage 9 assembly — one stray block from the drafter must not
    # delete every other section's work.
    out = render_block({"type": "mystery_block"})
    assert 'class="unknown-block"' in out
    assert 'data-block-type="mystery_block"' in out
    assert "[unknown block type: mystery_block]" in out


def test_paragraph_alias_renders_as_prose():
    # The drafter LLM frequently emits "paragraph" instead of the schema's
    # "prose" — accept it as a synonym so this common alias does not crash
    # the pipeline.
    out = render_block({"type": "paragraph", "text": "Hello **world**."})
    assert 'class="prose"' in out
    assert "<strong>world</strong>" in out
