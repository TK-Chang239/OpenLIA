"""Phase 2b tests for the v3 rendering pipeline.

Exercises:
  - chart_renderer produces PNG bytes for every supported chart_type
  - chart_renderer returns None on unrenderable input (empty data)
  - citation_rewriter maps [^source_id] -> [^N] and leaves unknowns alone
  - build_bibliography deduplicates by display_index and skips uncited rows
  - assemble_html produces a self-contained HTML doc with cover,
    sections in template order, chart images embedded as data URLs,
    and bibliography appended

No I/O; no server dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest
from openlia.llm.runtime.report_v3 import ChartSpec
from openlia.llm.runtime.report_v3.rendering import (
    assemble_html,
    build_bibliography,
    render_chart_png,
    rewrite_section_markdown,
)

# ---------------------------------------------------------------------------
# chart_renderer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chart_type,data",
    [
        ("line", [{"x": "2023", "y": 1.0}, {"x": "2024", "y": 2.5}]),
        ("area", [{"x": "Q1", "y": 5.0}, {"x": "Q2", "y": 4.2}]),
        ("bar", [{"label": "AAPL", "value": 3.0}, {"label": "MSFT", "value": 2.0}]),
        ("column", [{"label": "FY24", "value": 1.0}, {"label": "FY25", "value": 1.4}]),
        ("pie", [{"label": "Launch", "value": 60.0}, {"label": "Space", "value": 40.0}]),
        ("scatter", [{"x": 1.0, "y": 2.0}, {"x": 2.0, "y": 4.0}, {"x": 3.0, "y": 9.0}]),
        ("table", [{"label": "Revenue", "value": 1.2e9}, {"label": "EBITDA", "value": 2.4e8}]),
    ],
)
def test_render_chart_png_produces_png_bytes(chart_type, data):
    spec = ChartSpec(
        chart_id="c1",
        chart_type=chart_type,
        title=f"{chart_type} test",
        data=data,
    )
    rendered = render_chart_png(spec)
    assert rendered is not None
    assert rendered.chart_id == "c1"
    assert rendered.chart_type == chart_type
    assert rendered.png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_chart_png_returns_none_for_unrenderable_input():
    # All y values are non-numeric => no points to plot
    spec = ChartSpec(
        chart_id="c2",
        chart_type="line",
        title="bad",
        data=[{"x": "a", "y": "not a number"}],
    )
    assert render_chart_png(spec) is None


def test_render_chart_png_coerces_string_numerics():
    spec = ChartSpec(
        chart_id="c3",
        chart_type="bar",
        title="ok",
        data=[{"label": "x", "value": "1.5"}, {"label": "y", "value": "2.0"}],
    )
    rendered = render_chart_png(spec)
    assert rendered is not None
    assert rendered.png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# citation_rewriter
# ---------------------------------------------------------------------------


def test_rewrite_section_markdown_replaces_markers_with_display_index():
    out = rewrite_section_markdown(
        section_id="overview",
        title="Overview",
        markdown="Launch revenue grew [^web_1]. Backlog stable [^eodhd_3].",
        display_index_by_source_id={"web_1": 1, "eodhd_3": 2},
    )
    assert "[^1]" in out.markdown
    assert "[^2]" in out.markdown
    assert "[^web_1]" not in out.markdown
    assert "[^eodhd_3]" not in out.markdown
    assert set(out.cited_source_ids) == {"web_1", "eodhd_3"}


def test_rewrite_section_markdown_leaves_unknown_marker_in_place():
    out = rewrite_section_markdown(
        section_id="risks",
        title="Risks",
        markdown="Cite a ghost [^web_999].",
        display_index_by_source_id={"web_1": 1},
    )
    assert "[^web_999]" in out.markdown
    assert out.cited_source_ids == ("web_999",)


@dataclass
class _FakeCitation:
    source_id: str
    tool_name: str
    display_index: int | None
    provenance_json: str


def test_build_bibliography_skips_uncited_and_sorts_by_display_index():
    rows = [
        _FakeCitation(
            source_id="web_1",
            tool_name="web_search",
            display_index=2,
            provenance_json='{"url": "https://a.test", "title": "A"}',
        ),
        _FakeCitation(
            source_id="eodhd_1",
            tool_name="get_fundamentals",
            display_index=1,
            provenance_json='{"provider": "EODHD", "endpoint": "fundamentals", "period": "latest"}',
        ),
        _FakeCitation(
            source_id="web_2",
            tool_name="web_search",
            display_index=None,
            provenance_json='{"url": "https://b.test"}',
        ),
    ]
    bib = build_bibliography(rows)
    assert [e.display_index for e in bib] == [1, 2]
    assert bib[0].source_id == "eodhd_1"
    assert bib[1].source_id == "web_1"
    assert "EODHD" in bib[0].label
    assert bib[1].url == "https://a.test"


# ---------------------------------------------------------------------------
# assemble_html — end-to-end
# ---------------------------------------------------------------------------


@dataclass
class _FakeReport:
    subject: str
    template_id: str
    language: str


@dataclass
class _FakeSection:
    section_id: str
    section_index: int
    title: str
    markdown: str


@dataclass
class _FakeChart:
    chart_id: str
    chart_type: str
    title: str
    spec_json: str


def test_assemble_html_self_contained_with_chart_and_bibliography():
    report = _FakeReport(
        subject="RKLB.US",
        template_id="initiation",
        language="en",
    )
    chart_spec = ChartSpec(
        chart_id="trend",
        chart_type="line",
        title="Trend",
        data=[{"x": "2024", "y": 1.0}, {"x": "2025", "y": 2.0}],
    )
    sections = [
        _FakeSection(
            section_id="overview",
            section_index=0,
            title="Overview",
            markdown=(
                "RKLB launched Neutron [^web_1].\n\n{{chart:trend}}\n\n"
                "Margins improved [^eodhd_1]."
            ),
        ),
        _FakeSection(
            section_id="risks",
            section_index=1,
            title="Risks",
            markdown="Macro headwinds remain.",
        ),
    ]
    charts = [
        _FakeChart(
            chart_id="trend",
            chart_type="line",
            title="Trend",
            spec_json=chart_spec.model_dump_json(),
        )
    ]
    citations = [
        _FakeCitation(
            source_id="web_1",
            tool_name="web_search",
            display_index=1,
            provenance_json='{"url": "https://news.test/rklb", "title": "RKLB Q2"}',
        ),
        _FakeCitation(
            source_id="eodhd_1",
            tool_name="get_fundamentals",
            display_index=2,
            provenance_json='{"provider": "EODHD", "endpoint": "fundamentals"}',
        ),
    ]

    assembled = assemble_html(
        report=report,
        sections=sections,
        charts=charts,
        citations=citations,
        now=datetime(2026, 5, 27, 16, 0),
    )
    html = assembled.html

    assert html.startswith("<!DOCTYPE html>")
    assert "RKLB.US" in html
    # Cover meta strip
    assert "Template: initiation" in html
    # Sections in template order (overview before risks)
    assert html.index("Overview") < html.index("Risks")
    # Citation markers rewritten
    assert "[^1]" in html
    assert "[^2]" in html
    assert "[^web_1]" not in html
    # Chart inlined as data URL
    assert "src=\"data:image/png;base64," in html
    # Bibliography appended with both entries
    assert 'class="v3-bibliography"' in html
    assert "RKLB Q2" in html
    assert "EODHD fundamentals" in html
    # Bibliography URLs are hyperlinks
    assert 'href="https://news.test/rklb"' in html


def test_assemble_html_handles_missing_chart_gracefully():
    """When a chart spec is invalid the rendered HTML contains a fallback note."""
    report = _FakeReport(subject="X", template_id="initiation", language="en")
    sections = [
        _FakeSection(
            section_id="overview",
            section_index=0,
            title="Overview",
            markdown="See {{chart:missing}}",
        )
    ]
    charts = []  # the chart marker references a chart that wasn't emitted
    citations = []
    assembled = assemble_html(
        report=report,
        sections=sections,
        charts=charts,
        citations=citations,
    )
    assert "[chart not rendered: missing]" in assembled.html
