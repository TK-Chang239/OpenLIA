"""Block-level rendering tests for `routes/reports.py` PDF helpers.

Cover unit-level coverage of `_render_block` and `_schema_to_html` for
every Phase 13 block field-name fix (P1-01) so the HTML body that feeds
Playwright contains the right strings before we ever run a real browser.
"""

from __future__ import annotations

from openlia_server.routes.reports import (
    _furniture_template,
    _render_block,
    _schema_to_html,
)


def test_render_block_metric_cards_emits_label_value_and_delta():
    block = {
        "type": "metric_cards",
        "metrics": [
            {"label": "Revenue", "value": "$124B", "delta": "+10%", "delta_direction": "up"},
            {"label": "EPS", "value": "$1.46"},
        ],
    }
    html = _render_block(block)
    assert "Revenue" in html and "$124B" in html
    assert "EPS" in html and "$1.46" in html
    assert "+10%" in html
    assert "delta-up" in html


def test_render_block_table_uses_headers_and_keyed_rows():
    block = {
        "type": "table",
        "title": "Quarterly Snapshot",
        "headers": [
            {"key": "metric", "label": "Metric", "align": "left"},
            {"key": "value", "label": "Value", "align": "right"},
        ],
        "rows": [
            {"metric": "Revenue", "value": "$124B"},
            {"metric": "Operating Margin", "value": "32%"},
        ],
        "footnotes": ["Source: filings"],
    }
    html = _render_block(block)
    assert "Quarterly Snapshot" in html
    assert "Metric" in html and "Value" in html
    assert 'class="text-left"' in html
    assert 'class="text-right"' in html
    assert "Revenue" in html and "$124B" in html
    assert "Operating Margin" in html and "32%" in html
    assert "Source: filings" in html


def test_render_block_table_applies_row_style():
    block = {
        "type": "table",
        "title": "T",
        "headers": [{"key": "k", "label": "K", "align": "left"}],
        "rows": [{"k": "Total", "_row_style": "subtotal"}],
    }
    html = _render_block(block)
    assert "row-subtotal" in html


def test_render_block_cell_format_directional():
    block = {
        "type": "table",
        "title": "T",
        "headers": [{"key": "v", "label": "V", "align": "right"}],
        "rows": [{"v": "-10%"}, {"v": "5%"}],
        "cell_format": {"v": {"rule": "directional"}},
    }
    html = _render_block(block)
    assert "fmt-negative" in html
    assert "fmt-positive" in html


def test_render_block_key_finding_uses_content_field():
    block = {"type": "key_finding", "content": "Margins expanded to 32%."}
    html = _render_block(block)
    assert "Margins expanded to 32%." in html
    # Old fields must NOT leak in.
    assert "heading" not in html


def test_render_block_rating_badge_uses_rating_field():
    overweight = _render_block({"type": "rating_badge", "rating": "Overweight"})
    hold = _render_block({"type": "rating_badge", "rating": "Hold"})
    sell = _render_block({"type": "rating_badge", "rating": "Sell"})
    assert "Overweight" in overweight and "rating-buy" in overweight
    assert "Hold" in hold and "rating-hold" in hold
    assert "Sell" in sell and "rating-sell" in sell


def test_render_block_group_honours_columns():
    block = {
        "type": "group",
        "columns": 3,
        "blocks": [{"type": "text", "content": "a"}, {"type": "text", "content": "b"}],
    }
    html = _render_block(block)
    assert "group-cols-3" in html
    assert "repeat(3,minmax(0,1fr))" in html


def test_render_block_chart_emits_title_for_every_chart_type():
    for btype, extra in [
        ("line_chart", {"series": [{"name": "x", "data": [{"x": 1, "y": 2}]}]}),
        ("bar_chart", {"categories": ["A"], "series": [{"name": "x", "data": [1]}]}),
        ("area_chart", {"series": [{"name": "x", "data": [{"x": 1, "y": 2}]}]}),
        ("pie_chart", {"segments": [{"label": "A", "value": 1.0}]}),
        (
            "candlestick_chart",
            {"data": [{"date": "d", "open": 1, "high": 2, "low": 0, "close": 1}]},
        ),
        ("waterfall_chart", {"items": [{"label": "a", "value": 1, "type": "increase"}]}),
        ("scatter_plot", {"series": [{"name": "x", "data": [{"x": 1, "y": 2}]}]}),
        ("heatmap", {"x_labels": ["a"], "y_labels": ["b"], "values": [[1.0]]}),
        ("treemap", {"data": [{"name": "a", "value": 1}]}),
        (
            "combo_chart",
            {
                "categories": ["a"],
                "bar_series": [{"name": "b", "values": [1]}],
                "line_series": [{"name": "l", "values": [1]}],
            },
        ),
    ]:
        block = {"type": btype, "title": f"T-{btype}", **extra}
        html = _render_block(block)
        assert f"T-{btype}" in html, f"chart {btype} title missing"


def test_schema_to_html_renders_section_anchor_and_cover_zones():
    schema = {
        "schema_version": "2.0",
        "department": "secretary",
        "generated_at": "2026-04-24T00:00:00+00:00",
        "page_furniture": {
            "header": {"left": "OpenLIA", "right": "Secretary"},
            "footer": {"left": "Generated 2026-04-24", "center": "Page 1", "right": "Internal"},
            "disclaimer": "Not financial advice.",
        },
        "cover": {
            "title": "Apple Inc.",
            "subtitle": "Q1 2026",
            "ticker": "AAPL",
            "tagline": "Strong quarter.",
            "key_metrics": [{"label": "P", "value": "$198"}],
        },
        "rail": {
            "quick_stats": [{"label": "MktCap", "value": "$3T"}],
        },
        "sections": [
            {
                "id": "summary",
                "title": "Summary",
                "blocks": [{"type": "text", "content": "x"}],
            }
        ],
    }
    html = _schema_to_html(schema)
    assert 'id="summary"' in html
    assert "AAPL" in html
    assert "MktCap" in html and "$3T" in html
    assert "Not financial advice." in html


def test_furniture_template_emits_zones_and_returns_none_when_empty():
    tpl = _furniture_template({"left": "L", "center": "C", "right": "R"}, kind="header")
    assert tpl is not None
    assert "L" in tpl and "C" in tpl and "R" in tpl
    assert 'data-furniture-kind="header"' in tpl
    assert _furniture_template(None, kind="header") is None
    assert _furniture_template({"left": ""}, kind="footer") is None
