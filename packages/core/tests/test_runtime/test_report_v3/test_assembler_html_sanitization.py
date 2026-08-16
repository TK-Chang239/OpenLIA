"""Stage 2.5 — sanitization consistency for the v3 HTML assembler.

The ``/html`` and ``/pdf`` outputs must neutralise raw HTML written by
the model into its section text (parity with the DOCX path, which uses
``html: False``, and the browser renderer, which escapes). Trusted chart
``<figure>`` blocks the assembler injects itself must still render.

The three forked assemblers (report_v3 / report_eu / report_mb) are
byte-identical; testing the v3 fork covers all three.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from openlia.llm.runtime.report_v3 import ChartSpec
from openlia.llm.runtime.report_v3.rendering import assemble_html


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


def _report() -> _FakeReport:
    return _FakeReport(subject="ACME", template_id="initiation", language="en")


def test_model_authored_html_is_escaped_not_rendered():
    """Raw HTML in section markdown is neutralised (escaped)."""
    sections = [
        _FakeSection(
            section_id="overview",
            section_index=0,
            title="Overview",
            markdown=(
                "Analysis begins.\n\n"
                "<script>alert('xss')</script>\n\n"
                '<img src="x" onerror="alert(1)">\n\n'
                "<b>bolded via raw html</b>\n"
            ),
        )
    ]
    assembled = assemble_html(
        report=_report(),
        sections=sections,
        charts=[],
        citations=[],
        now=datetime(2026, 8, 16, 12, 0),
    )
    html = assembled.html

    # No live raw-HTML elements from the model reach the output.
    assert "<script>" not in html
    assert '<img src="x" onerror="alert(1)">' not in html
    assert "<b>bolded via raw html</b>" not in html
    # They survive only as escaped, inert text.
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html
    assert "&lt;b&gt;bolded via raw html&lt;/b&gt;" in html


def test_trusted_chart_figure_still_renders():
    """The assembler's own ``<figure>`` chart block renders as real HTML."""
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
            markdown="Intro line.\n\n{{chart:trend}}\n\nOutro line.",
        )
    ]
    charts = [
        _FakeChart(
            chart_id="trend",
            chart_type="line",
            title="Trend",
            spec_json=chart_spec.model_dump_json(),
        )
    ]
    assembled = assemble_html(
        report=_report(),
        sections=sections,
        charts=charts,
        citations=[],
        now=datetime(2026, 8, 16, 12, 0),
    )
    html = assembled.html

    # Chart figure rendered as real HTML with an inline data URL...
    assert '<figure class="v3-chart">' in html
    assert 'src="data:image/png;base64,' in html
    # ...and the standalone marker paragraph is not left nested in a <p>.
    assert "<p><figure" not in html
    assert "{{chart:trend}}" not in html


def test_markdown_tables_still_render_with_html_disabled():
    """Disabling raw-HTML passthrough must not disable markdown tables."""
    sections = [
        _FakeSection(
            section_id="metrics",
            section_index=0,
            title="Metrics",
            markdown=("| Metric | Value |\n| --- | --- |\n| Revenue | 100 |\n"),
        )
    ]
    assembled = assemble_html(
        report=_report(),
        sections=sections,
        charts=[],
        citations=[],
        now=datetime(2026, 8, 16, 12, 0),
    )
    html = assembled.html
    assert "<table>" in html
    assert "<td>Revenue</td>" in html
