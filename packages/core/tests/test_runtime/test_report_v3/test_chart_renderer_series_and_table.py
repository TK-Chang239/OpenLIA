"""Regression tests for the two audit-critical chart renderer defects.

C2 — a line spec whose points carry a ``series`` field must be drawn as
one line per series over shared, deduplicated x categories (previously
all points were concatenated into a single line whose x-axis repeated
the category list once per series).

C3 — a table spec with pre-formatted string values ("$126.38") must
preserve those strings in the rendered cells (previously values were
coerced through float() and any non-numeric string rendered as "").
"""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from openlia.llm.runtime.report_v3.rendering.chart_renderer import (  # noqa: E402
    _draw,
    render_chart_png,
)
from openlia.llm.runtime.report_v3.schemas import ChartSpec  # noqa: E402

_FYS = ["FY2022", "FY2023", "FY2024", "FY2025", "FY2026"]


def _two_series_spec() -> ChartSpec:
    data = [{"x": fy, "y": (i + 1) * 10.0, "series": "Revenue"} for i, fy in enumerate(_FYS)]
    data += [{"x": fy, "y": (i + 1) * 2.0, "series": "Free Cash Flow"} for i, fy in enumerate(_FYS)]
    return ChartSpec(
        chart_id="c",
        chart_type="line",
        title="Revenue and FCF",
        data=data,
        axes={"y": "USD"},
    )


def test_line_chart_draws_one_line_per_series() -> None:
    spec = _two_series_spec()
    fig, ax = plt.subplots()
    try:
        assert _draw(ax, spec, list(spec.data)) is True
        assert len(ax.lines) == 2
        labels = [str(t.get_text()) for t in ax.get_xticklabels()]
        assert labels == _FYS  # deduplicated categories, not repeated per series
        legend = ax.get_legend()
        assert legend is not None
        legend_texts = {t.get_text() for t in legend.get_texts()}
        assert legend_texts == {"Revenue", "Free Cash Flow"}
    finally:
        plt.close(fig)


def test_single_series_line_unchanged_no_legend() -> None:
    spec = ChartSpec(
        chart_id="c",
        chart_type="line",
        title="t",
        data=[{"x": fy, "y": float(i)} for i, fy in enumerate(_FYS)],
        axes={},
    )
    fig, ax = plt.subplots()
    try:
        assert _draw(ax, spec, list(spec.data)) is True
        assert len(ax.lines) == 1
        assert ax.get_legend() is None
    finally:
        plt.close(fig)


def test_large_values_do_not_use_scientific_offset() -> None:
    spec = ChartSpec(
        chart_id="c",
        chart_type="line",
        title="t",
        data=[{"x": fy, "y": 2.0e11 + i * 1e10} for i, fy in enumerate(_FYS)],
        axes={},
    )
    fig, ax = plt.subplots()
    try:
        assert _draw(ax, spec, list(spec.data)) is True
        fig.canvas.draw()
        tick_texts = [t.get_text() for t in ax.get_yticklabels()]
        assert any("B" in t or "T" in t for t in tick_texts), tick_texts
        assert ax.yaxis.get_offset_text().get_text() in ("", None)
    finally:
        plt.close(fig)


def test_table_chart_preserves_string_values() -> None:
    spec = ChartSpec(
        chart_id="c",
        chart_type="table",
        title="Valuation summary",
        data=[
            {"label": "DCF fair value / share", "value": "$126.38"},
            {"label": "EV/EBITDA implied EV", "value": "$3.48T"},
            {"label": "Current market cap", "value": "$5.45T"},
        ],
        axes={},
    )
    fig, ax = plt.subplots()
    try:
        assert _draw(ax, spec, list(spec.data)) is True
        assert ax.tables
        cell_texts = {c.get_text().get_text() for c in ax.tables[0].get_celld().values()}
        assert "$126.38" in cell_texts
        assert "$3.48T" in cell_texts
    finally:
        plt.close(fig)


def test_table_chart_still_formats_numeric_values() -> None:
    spec = ChartSpec(
        chart_id="c",
        chart_type="table",
        title="t",
        data=[{"label": "Revenue", "value": 1_200_000_000}],
        axes={},
    )
    fig, ax = plt.subplots()
    try:
        assert _draw(ax, spec, list(spec.data)) is True
        cell_texts = {c.get_text().get_text() for c in ax.tables[0].get_celld().values()}
        assert "1.20B" in cell_texts
    finally:
        plt.close(fig)


def test_render_chart_png_end_to_end_multiseries() -> None:
    rendered = render_chart_png(_two_series_spec())
    assert rendered is not None
    assert rendered.png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
