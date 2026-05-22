"""waterfall_chart — bridge visualization showing contributions to a total.

Registered name: "waterfall_chart"

Renders a multi-step waterfall (bridge) chart visualizing how a starting value
is built up (or torn down) through a series of drivers to reach an ending value.
Classic use: NI bridge (Revenue -> COGS -> OpEx -> Tax -> NI), FY-to-FY revenue
bridge, EPS walk.

Produces:
- Plotly JSON (html field)
- Markdown table with all steps and cumulative running total

Design ref: planning/2026-05-21-equity-research-helpers-design.md §3.7
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

_COLOR_MAP: dict[str, str] = {
    "positive": "seagreen",
    "negative": "indianred",
    "neutral": "steelblue",
    "start": "steelblue",
    "end": "steelblue",
}


def _classify_color(delta: float, color_hint: str | None) -> str:
    if color_hint and color_hint in _COLOR_MAP:
        return _COLOR_MAP[color_hint]
    if delta >= 0:
        return _COLOR_MAP["positive"]
    return _COLOR_MAP["negative"]


def _compute_steps(
    starting_value: float,
    drivers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute cumulative running totals and floating bar bases for each step.

    Returns list of step dicts with:
        label, delta, running_total, base (for floating bars), color
    """
    steps: list[dict[str, Any]] = []
    running = starting_value

    for d in drivers:
        label: str = d["label"]
        delta: float = float(d["delta"])
        color_hint: str | None = d.get("color_hint")
        base = running if delta >= 0 else running + delta
        running += delta
        steps.append(
            {
                "label": label,
                "delta": delta,
                "running_total": running,
                "base": base,
                "color": _classify_color(delta, color_hint),
            }
        )

    return steps


def _build_markdown_table(
    starting_label: str,
    starting_value: float,
    steps: list[dict[str, Any]],
    ending_label: str,
    ending_value: float,
) -> str:
    header = "| Step | Delta | Running Total |"
    separator = "|---|---|---|"
    rows: list[str] = [
        f"| **{starting_label}** | — | {starting_value:,.2f} |",
    ]
    for s in steps:
        sign = "+" if s["delta"] >= 0 else ""
        rows.append(f"| {s['label']} | {sign}{s['delta']:,.2f} | {s['running_total']:,.2f} |")
    rows.append(f"| **{ending_label}** | — | {ending_value:,.2f} |")
    return "\n".join([header, separator, *rows])


def _build_plotly_json(
    starting_label: str,
    starting_value: float,
    steps: list[dict[str, Any]],
    ending_label: str,
    ending_value: float,
    title: str,
) -> str:
    try:
        import plotly.graph_objects as go  # type: ignore[import-untyped]

        all_labels = [starting_label] + [s["label"] for s in steps] + [ending_label]

        # measures: "absolute" for start/end, "relative" for drivers
        measures = ["absolute"] + ["relative"] * len(steps) + ["total"]

        # y values: starting, then per-driver deltas, then 0 (total is recomputed by Plotly)
        y_values = [starting_value] + [s["delta"] for s in steps] + [ending_value]

        fig = go.Figure(
            go.Waterfall(
                name="Bridge",
                orientation="v",
                measure=measures,
                x=all_labels,
                y=y_values,
                connector={"line": {"color": "rgb(63,63,63)"}},
                increasing={"marker": {"color": _COLOR_MAP["positive"]}},
                decreasing={"marker": {"color": _COLOR_MAP["negative"]}},
                totals={"marker": {"color": _COLOR_MAP["end"]}},
                textposition="outside",
                text=[
                    f"{starting_value:,.0f}",
                    *[f"{s['delta']:+,.0f}" for s in steps],
                    f"{ending_value:,.0f}",
                ],
            )
        )
        fig.update_layout(
            title=title,
            yaxis_title="Value",
            showlegend=False,
            margin={"l": 60, "r": 40, "t": 60, "b": 80},
        )
        return fig.to_json()

    except ImportError:
        return json.dumps(
            {
                "error": "plotly_not_installed",
                "data": [],
                "layout": {"title": {"text": title}},
            }
        )


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    starting_value: float,
    starting_label: str,
    drivers: list[dict[str, Any]],
    ending_label: str,
    ending_value: float | None = None,
    title: str = "Bridge Chart",
    tolerance: float = 0.01,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Render a waterfall bridge chart.

    Args:
        starting_value: Value at the start of the bridge.
        starting_label: Label for the starting bar (e.g. "FY24 Revenue").
        drivers: List of {label, delta, color_hint} dicts.
            - label (str): Driver name shown on chart.
            - delta (float): Positive = tailwind, negative = headwind.
            - color_hint (str | None): "positive", "negative", or "neutral".
              Defaults to sign-based coloring.
        ending_label: Label for the ending total bar.
        ending_value: Expected end value (optional). If provided, validated against
            starting_value + sum(deltas) within tolerance.
        title: Chart title.
        tolerance: Fractional tolerance for ending_value validation (default 1%).
        data_as_of: ISO date string.
        source_provenance: List of upstream citation IDs.

    Returns:
        dict with html (Plotly JSON), markdown_table, summary stats, metadata.
    """
    if not drivers:
        raise ValueError("drivers must be non-empty")
    for i, d in enumerate(drivers):
        if "label" not in d:
            raise ValueError(f"Driver {i}: missing 'label'")
        if "delta" not in d:
            raise ValueError(f"Driver {d.get('label', i)!r}: missing 'delta'")

    steps = _compute_steps(starting_value, drivers)
    computed_end = starting_value + sum(float(d["delta"]) for d in drivers)

    warnings: list[str] = []

    if ending_value is not None:
        diff = abs(computed_end - ending_value)
        relative_diff = diff / abs(ending_value) if ending_value != 0 else diff
        if relative_diff > tolerance:
            warnings.append(
                f"ending_value {ending_value:,.2f} does not match "
                f"starting_value + sum(deltas) = {computed_end:,.2f} "
                f"(diff={diff:,.2f}, tolerance={tolerance:.1%}). "
                "Check inputs."
            )
        actual_end = ending_value
    else:
        actual_end = computed_end

    total_change = actual_end - starting_value
    total_change_pct = (total_change / starting_value * 100) if starting_value != 0 else 0.0

    positive_drivers = [
        {"label": d["label"], "delta": float(d["delta"])} for d in drivers if float(d["delta"]) > 0
    ]
    negative_drivers = [
        {"label": d["label"], "delta": float(d["delta"])} for d in drivers if float(d["delta"]) < 0
    ]

    markdown_table = _build_markdown_table(
        starting_label, starting_value, steps, ending_label, actual_end
    )
    html = _build_plotly_json(
        starting_label, starting_value, steps, ending_label, actual_end, title
    )

    return {
        "chart_type": "waterfall",
        "html": html,
        "markdown_table": markdown_table,
        "summary": {
            "starting_label": starting_label,
            "starting_value": starting_value,
            "ending_label": ending_label,
            "ending_value": actual_end,
            "total_change": total_change,
            "total_change_pct": round(total_change_pct, 2),
            "positive_drivers": positive_drivers,
            "negative_drivers": negative_drivers,
            "driver_count": len(drivers),
        },
        "steps": steps,
        "title": title,
        "warnings": warnings,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="waterfall_chart",
        category=Category.OUTPUT,
        one_liner=(
            "Waterfall bridge chart: visualizes step-by-step contributions "
            "from a starting value to an ending value. Plotly JSON + markdown table."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Visualize how a sequence of drivers (positive and negative) build from "
            "a starting value to an ending value. Classic uses: revenue bridge (FY-to-FY), "
            "EPS walk (GAAP NI decomposition), FCF bridge, or NI attribution waterfall."
        ),
        when_to_use=[
            "FY-over-FY revenue, EBITDA, EPS, or FCF attribution bridge.",
            "NI decomposition: Revenue → COGS → Gross → OpEx → EBIT → Tax → NI.",
            "Any multi-step decomposition where the audience needs to follow the math.",
        ],
        when_not_to_use=[
            "Time-series trend charts — use chart_builder instead.",
            "Two-variable sensitivity — use sensitivity_table.",
            "Valuation range comparisons across methodologies — use football_field_chart.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "starting_value": HelperParam(
                type="float",
                description="Numeric value at the start of the bridge.",
                required=True,
            ),
            "starting_label": HelperParam(
                type="str",
                description="Label for the starting bar, e.g. 'FY24 Revenue'.",
                required=True,
            ),
            "drivers": HelperParam(
                type="list[dict]",
                description=(
                    "List of {label, delta, color_hint} dicts. "
                    "delta is positive for tailwinds, negative for headwinds. "
                    "color_hint is optional: 'positive', 'negative', or 'neutral'."
                ),
                required=True,
            ),
            "ending_label": HelperParam(
                type="str",
                description="Label for the ending total bar, e.g. 'FY25 Revenue'.",
                required=True,
            ),
            "ending_value": HelperParam(
                type="float",
                default=None,
                description=(
                    "Expected ending value. If provided, validated against "
                    "starting_value + sum(deltas) within tolerance."
                ),
                required=False,
            ),
            "title": HelperParam(
                type="str",
                default="Bridge Chart",
                description="Chart title.",
                required=False,
            ),
            "tolerance": HelperParam(
                type="float",
                default=0.01,
                description="Fractional tolerance for ending_value validation.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="waterfall_chart_output",
                type="waterfall_chart_output",
                description=(
                    "html (Plotly JSON), markdown_table, summary with total_change "
                    "and driver breakdowns, steps list with running totals."
                ),
            ),
        ],
        produces_artifacts=["waterfall_chart_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
