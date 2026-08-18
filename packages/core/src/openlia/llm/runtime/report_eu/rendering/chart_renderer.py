"""Render a v3 ``ChartSpec`` to PNG bytes via matplotlib.

Pure function — no I/O, no storage decisions. Callers handle
persistence (write to disk OR embed as base64 data URL OR cache).

Supports the seven chart types the v3 schema enumerates:

  - line / area     time-series-ish: x is a label or numeric, y is numeric
  - bar / column    categorical: label on one axis, value on the other
                    (bar = horizontal, column = vertical)
  - pie             categorical: label slices weighted by value
  - scatter         numeric pairs: x and y both numeric
  - table           rendered as a rasterized matplotlib table — kept
                    simple; HTML callers may also choose to substitute
                    a native ``<table>`` instead of this image.

The renderer is deliberately permissive: any v3 ``ChartDataPoint``
field can carry the value (label/x/y/value), and string numerics are
coerced. When the spec is unusable (empty data, all-None values), the
renderer returns ``None`` and the caller falls back to "[chart not
rendered]" text in the HTML.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from ..schemas import ChartDataPoint, ChartSpec


@dataclass(frozen=True)
class RenderedChart:
    """PNG bytes + the source ChartSpec for the caller's bookkeeping."""

    chart_id: str
    chart_type: str
    png_bytes: bytes
    title: str


def render_chart_png(chart: ChartSpec) -> RenderedChart | None:
    """Render ``chart`` to PNG bytes; return None when not renderable.

    The matplotlib import is local so test environments without it
    fall back to text-only HTML.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    points = list(chart.data)
    if not points:
        return None

    fig, ax = plt.subplots(figsize=(6.5, 3.6), dpi=150)
    try:
        ok = _draw(ax, chart, points)
    except _NotRenderable:
        plt.close(fig)
        return None
    if not ok:
        plt.close(fig)
        return None

    _apply_axes_labels(ax, chart)
    ax.set_title(chart.title, fontsize=11)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    return RenderedChart(
        chart_id=chart.chart_id,
        chart_type=chart.chart_type,
        png_bytes=buf.getvalue(),
        title=chart.title,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


class _NotRenderable(RuntimeError):
    """Raised when a chart's data shape doesn't fit the chosen chart_type."""


def _draw(ax, chart: ChartSpec, points: list[ChartDataPoint]) -> bool:
    """Dispatch to the per-type drawer. Returns False if rendering failed."""
    t = chart.chart_type
    if t in ("line", "area"):
        return _draw_line_or_area(ax, points, fill=(t == "area"))
    if t in ("bar", "column"):
        return _draw_bar(ax, points, horizontal=(t == "bar"))
    if t == "pie":
        return _draw_pie(ax, points)
    if t == "scatter":
        return _draw_scatter(ax, points)
    if t == "table":
        return _draw_table(ax, points)
    return False


def _draw_line_or_area(ax, points: list[ChartDataPoint], *, fill: bool) -> bool:
    """One plotted line per ``series`` value over a shared x axis.

    Points without a ``series`` field form a single unnamed series, which
    preserves the old single-line behavior. String x values become one
    deduplicated, first-seen-ordered category axis shared by all series.
    """
    series_points: dict[str | None, list[tuple[float | str | None, float]]] = {}
    series_order: list[str | None] = []
    for p in points:
        y = _coerce_y(p)
        if y is None:
            continue
        key = _coerce_series(p)
        if key not in series_points:
            series_points[key] = []
            series_order.append(key)
        series_points[key].append((_coerce_x(p), y))
    if not series_points:
        raise _NotRenderable("no numeric y values")

    xs_all = [x for pts in series_points.values() for x, _ in pts]
    categorical = bool(xs_all) and all(isinstance(x, str) for x in xs_all)

    if categorical:
        categories: list[str] = []
        index_of: dict[str, int] = {}
        for x in xs_all:
            if x not in index_of:
                index_of[x] = len(categories)
                categories.append(x)
        for key in series_order:
            pts = series_points[key]
            idxs = [index_of[x] for x, _ in pts]
            ys = [y for _, y in pts]
            (line,) = ax.plot(idxs, ys, marker="o", label=key or "")
            if fill:
                ax.fill_between(idxs, ys, alpha=0.2, color=line.get_color())
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories, rotation=20, ha="right")
    else:
        for key in series_order:
            pts = series_points[key]
            xs = [
                float(x) if isinstance(x, (int, float)) else float(i)
                for i, (x, _) in enumerate(pts)
            ]
            ys = [y for _, y in pts]
            (line,) = ax.plot(xs, ys, marker="o", label=key or "")
            if fill:
                ax.fill_between(xs, ys, alpha=0.2, color=line.get_color())

    if len(series_order) > 1:
        ax.legend(fontsize=8)
    _apply_value_axis_format(ax.yaxis)
    return True


def _draw_bar(ax, points: list[ChartDataPoint], *, horizontal: bool) -> bool:
    labels: list[str] = []
    values: list[float] = []
    for p in points:
        label = _coerce_label(p)
        value = _coerce_value(p)
        if value is None:
            continue
        labels.append(label or f"#{len(labels) + 1}")
        values.append(value)
    if not values:
        raise _NotRenderable("no numeric values")
    indices = range(len(values))
    if horizontal:
        ax.barh(list(indices), values)
        ax.set_yticks(list(indices))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        _apply_value_axis_format(ax.xaxis)
    else:
        ax.bar(list(indices), values)
        ax.set_xticks(list(indices))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        _apply_value_axis_format(ax.yaxis)
    return True


def _draw_pie(ax, points: list[ChartDataPoint]) -> bool:
    labels: list[str] = []
    values: list[float] = []
    for p in points:
        v = _coerce_value(p)
        if v is None or v <= 0:
            continue
        labels.append(_coerce_label(p) or f"#{len(labels) + 1}")
        values.append(v)
    if not values:
        raise _NotRenderable("no positive values")
    ax.pie(values, labels=labels, autopct="%1.1f%%")
    ax.set_aspect("equal")
    return True


def _draw_scatter(ax, points: list[ChartDataPoint]) -> bool:
    xs: list[float] = []
    ys: list[float] = []
    for p in points:
        x = _coerce_x_numeric(p)
        y = _coerce_y(p)
        if x is None or y is None:
            continue
        xs.append(x)
        ys.append(y)
    if not xs:
        raise _NotRenderable("no numeric (x, y) pairs")
    ax.scatter(xs, ys)
    return True


def _draw_table(ax, points: list[ChartDataPoint]) -> bool:
    """Render a small two-column (label, value) table as text on the axes.

    HTML callers may also substitute a native ``<table>`` for table
    charts; this rasterized form is the fallback for PDF / image
    contexts where inline HTML is not available.
    """
    rows: list[tuple[str, str]] = []
    for p in points:
        label = _coerce_label(p) or _coerce_x_str(p) or ""
        # Tables are text: pre-formatted string values ("$126.38", "12.4x")
        # must survive verbatim — only bare numerics get formatted.
        raw = p.value if p.value is not None else p.y
        if isinstance(raw, str):
            cell = raw.strip()
        elif raw is None:
            cell = ""
        else:
            cell = _format_value(float(raw))
        rows.append((label, cell))
    if not rows:
        raise _NotRenderable("no rows")
    ax.axis("off")
    table = ax.table(
        cellText=[[lbl, val] for (lbl, val) in rows],
        colLabels=["", ""],
        loc="center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    return True


def _apply_axes_labels(ax, chart: ChartSpec) -> None:
    x_label = chart.axes.get("x") or chart.axes.get("x_label")
    y_label = chart.axes.get("y") or chart.axes.get("y_label")
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)


# ---------------------------------------------------------------------------
# Coercion helpers — permissive per spec decision #7
# ---------------------------------------------------------------------------


def _coerce_series(p: ChartDataPoint) -> str | None:
    s = getattr(p, "series", None)
    if s is None:
        return None
    s = str(s).strip()
    return s or None


def _apply_value_axis_format(axis) -> None:
    """Human-readable value ticks (200B, 1.5T) instead of the matplotlib
    scientific offset ("1e11")."""
    from matplotlib.ticker import FuncFormatter

    axis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_axis_value(v)))


def _format_axis_value(v: float) -> str:
    if abs(v) >= 1e12:
        return f"{v / 1e12:g}T"
    if abs(v) >= 1e9:
        return f"{v / 1e9:g}B"
    if abs(v) >= 1e6:
        return f"{v / 1e6:g}M"
    if abs(v) >= 1e3:
        return f"{v / 1e3:g}K"
    return f"{v:g}"


def _coerce_label(p: ChartDataPoint) -> str | None:
    if p.label is not None:
        return str(p.label)
    if isinstance(p.x, str):
        return p.x
    return None


def _coerce_value(p: ChartDataPoint) -> float | None:
    for candidate in (p.value, p.y):
        v = _to_float(candidate)
        if v is not None:
            return v
    return None


def _coerce_y(p: ChartDataPoint) -> float | None:
    for candidate in (p.y, p.value):
        v = _to_float(candidate)
        if v is not None:
            return v
    return None


def _coerce_x(p: ChartDataPoint) -> float | str | None:
    if p.x is None:
        return p.label
    if isinstance(p.x, str):
        v = _to_float(p.x)
        return v if v is not None else p.x
    return float(p.x)


def _coerce_x_numeric(p: ChartDataPoint) -> float | None:
    return _to_float(p.x)


def _coerce_x_str(p: ChartDataPoint) -> str | None:
    if p.x is None:
        return None
    return str(p.x)


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def _format_value(v: float | None) -> str:
    if v is None:
        return ""
    if abs(v) >= 1_000_000_000:
        return f"{v / 1_000_000_000:,.2f}B"
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:,.2f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:,.1f}K"
    if abs(v) < 1:
        return f"{v:.3f}"
    return f"{v:,.2f}"
