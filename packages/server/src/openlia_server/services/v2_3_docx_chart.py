"""Native chart graphics for the v2.3 docx renderer via embedded PNG.

python-docx 1.x exposes no Chart object, so we render each
``ChartSpec`` with matplotlib (which is already a project dependency
because the v1/v2.2 renderers also use it for charts) and embed the
resulting PNG via ``Document.add_picture``. The result is a real
graphic inside Word — pannable, exportable, copy-paste-able — instead
of a data table that asks the reader to mentally plot the shape.

The data-table view is kept as a fallback when matplotlib is missing
or the chart's data can't be reshaped into a renderable form, so the
report never silently drops a figure.
"""

from __future__ import annotations

import io
from typing import Any

from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    BundleSeries,
    ChartSpec,
    ChartType,
    ResearchBundle,
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def try_render_chart_png(chart: ChartSpec, bundle: ResearchBundle) -> bytes | None:
    """Return PNG bytes for the chart, or None if rendering is impossible.

    Callers fall back to a data table when this returns None.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # pragma: no cover — matplotlib is a hard dep, but
        # defensive in case a future build slims it out.
        return None

    try:
        categories, series_values = _collect_data(chart, bundle)
    except _NotRenderable:
        return None
    if not categories or not series_values:
        return None

    fig, ax = plt.subplots(figsize=(6.0, 3.4), dpi=150)
    try:
        _draw(ax, chart, categories, series_values)
        ax.set_title(chart.title)
        if chart.x_axis_label:
            ax.set_xlabel(chart.x_axis_label)
        if chart.y_axis_label:
            ax.set_ylabel(chart.y_axis_label)
        if len(series_values) > 1 and chart.chart_type != ChartType.PIE:
            ax.legend([name for name, _vals in series_values])
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        return buf.getvalue()
    finally:
        plt.close(fig)


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


class _NotRenderable(Exception):
    pass


def _collect_data(
    chart: ChartSpec, bundle: ResearchBundle
) -> tuple[list[str], list[tuple[str, list[float]]]]:
    """Reshape chart series into ``(categories, [(name, values)...])``.

    Two layouts are accepted:

    1. Single fact_id per series that points at a ``BundleSeries`` —
       the series points map 1:1 to ``chart.category_labels`` by index.
    2. One fact_id per category in the series — each fact's scalar
       value fills the cell at that index.

    Anything else falls back to data-table rendering.
    """
    categories = list(chart.category_labels)
    output: list[tuple[str, list[float]]] = []
    for series in chart.series:
        values = _series_values(series, bundle, len(categories))
        if values is None:
            raise _NotRenderable()
        output.append((series.name, values))
    return categories, output


def _series_values(series: Any, bundle: ResearchBundle, n: int) -> list[float] | None:
    if len(series.value_fact_ids) == 1:
        fact = bundle.facts.get(series.value_fact_ids[0])
        if fact is not None and isinstance(fact.value, BundleSeries):
            if len(fact.value.points) != n:
                return None
            return [p.value for p in fact.value.points]
    if len(series.value_fact_ids) != n:
        return None
    out: list[float] = []
    for fid in series.value_fact_ids:
        fact = bundle.facts.get(fid)
        if fact is None or not isinstance(fact.value, (int, float)):
            return None
        out.append(float(fact.value))
    return out


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def _draw(
    ax: Any,
    chart: ChartSpec,
    categories: list[str],
    series: list[tuple[str, list[float]]],
) -> None:
    ct = chart.chart_type

    if ct == ChartType.PIE:
        # Only the first series is meaningful for a pie chart.
        name, values = series[0]
        ax.pie(values, labels=categories, autopct="%1.1f%%")
        ax.set_aspect("equal")
        return

    if ct == ChartType.LINE:
        for name, values in series:
            ax.plot(categories, values, marker="o", label=name)
        return

    if ct == ChartType.AREA:
        for name, values in series:
            ax.fill_between(categories, values, alpha=0.4, label=name)
            ax.plot(categories, values)
        return

    if ct == ChartType.SCATTER:
        x_indices = list(range(len(categories)))
        for name, values in series:
            ax.scatter(x_indices, values, label=name)
        ax.set_xticks(x_indices)
        ax.set_xticklabels(categories)
        return

    # COLUMN (vertical bars) and BAR (horizontal) — group multiple series.
    if ct == ChartType.BAR:
        _grouped_bar(ax, categories, series, horizontal=True)
        return

    # Default to vertical column bars for COLUMN or anything we didn't
    # special-case above.
    _grouped_bar(ax, categories, series, horizontal=False)


def _grouped_bar(
    ax: Any,
    categories: list[str],
    series: list[tuple[str, list[float]]],
    *,
    horizontal: bool,
) -> None:
    import numpy as np

    n_series = len(series)
    x = np.arange(len(categories))
    width = 0.8 / max(n_series, 1)
    for i, (name, values) in enumerate(series):
        offset = (i - (n_series - 1) / 2) * width
        if horizontal:
            ax.barh(x + offset, values, height=width, label=name)
        else:
            ax.bar(x + offset, values, width=width, label=name)
    if horizontal:
        ax.set_yticks(x)
        ax.set_yticklabels(categories)
    else:
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=20, ha="right")


__all__ = ["try_render_chart_png"]


# Touch BundleFact so future refactors that drop the import notice.
_ = BundleFact
