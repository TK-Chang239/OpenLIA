"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: (new file — not vendored from upstream)
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via SCHEMA module-level constant and an
execute(**params) entry point.
"""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperSchema,
    register_library_helper,
)

SCHEMA = HelperSchema(
    name="make_chart",
    description="Render a matplotlib chart and return as inline SVG.",
    params={
        "chart_type": HelperParam(
            type="str",
            description="Chart type: line, bar, scatter, heatmap.",
            required=True,
        ),
        "series": HelperParam(
            type="list",
            description="Data series. Each element is {label, x, y} or just a list of values.",
            required=True,
        ),
        "x_label": HelperParam(
            type="str",
            default="",
            description="X axis label.",
            required=False,
        ),
        "y_label": HelperParam(
            type="str",
            default="",
            description="Y axis label.",
            required=False,
        ),
        "title": HelperParam(
            type="str",
            default="",
            description="Chart title.",
            required=False,
        ),
    },
)


def execute(**params: Any) -> dict[str, Any]:
    """Render chart and return SVG string.

    Params:
        chart_type: 'line' | 'bar' | 'scatter' | 'heatmap'
        series: list of series dicts {label, x, y} or list of y-values
        x_label, y_label, title: optional strings
    """
    chart_type = params["chart_type"]
    series = params["series"]
    x_label = params.get("x_label", "")
    y_label = params.get("y_label", "")
    title = params.get("title", "")

    fig, ax = plt.subplots()

    if chart_type == "bar":
        for s in series:
            if isinstance(s, dict):
                ax.bar(s.get("x", list(range(len(s["y"])))), s["y"], label=s.get("label", ""))
            else:
                ax.bar(list(range(len(s))), s)
    elif chart_type == "scatter":
        for s in series:
            if isinstance(s, dict):
                ax.scatter(s.get("x", []), s.get("y", []), label=s.get("label", ""))
    else:
        # line (default)
        for s in series:
            if isinstance(s, dict):
                ax.plot(s.get("x", list(range(len(s["y"])))), s["y"], label=s.get("label", ""))
            else:
                ax.plot(s)

    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)
    if title:
        ax.set_title(title)
    if any(isinstance(s, dict) and s.get("label") for s in series):
        ax.legend()

    buf = io.StringIO()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    return {"format": "svg_inline", "svg": buf.getvalue()}


register_library_helper("make_chart", execute, SCHEMA)
