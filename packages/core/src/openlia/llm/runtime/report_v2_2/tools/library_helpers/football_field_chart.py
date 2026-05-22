"""football_field_chart — multi-methodology valuation range visualization.

Registered name: "football_field_chart"

Renders a horizontal bar chart showing the [low, high] range for each valuation
methodology, with the median marked as a tick and the current price as a vertical
line. Also produces a markdown table of the same data.

Design ref: planning/2026-05-21-equity-research-helpers-design.md §3.6
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
# Core logic — chart data
# ---------------------------------------------------------------------------


def _median_of_medians(methodologies: list[dict[str, Any]]) -> float | None:
    """Compute median of per-methodology medians."""
    medians = [float(m["median"]) for m in methodologies if m.get("median") is not None]
    if not medians:
        return None
    sorted_m = sorted(medians)
    n = len(sorted_m)
    mid = n // 2
    if n % 2 == 1:
        return sorted_m[mid]
    return (sorted_m[mid - 1] + sorted_m[mid]) / 2.0


def _current_price_position(
    current_price: float, methodologies: list[dict[str, Any]]
) -> str:
    """Describe where current price falls relative to the overall range."""
    all_lows = [float(m["low"]) for m in methodologies if m.get("low") is not None]
    all_highs = [float(m["high"]) for m in methodologies if m.get("high") is not None]
    if not all_lows or not all_highs:
        return "unknown"
    overall_low = min(all_lows)
    overall_high = max(all_highs)
    if current_price < overall_low:
        return "below range"
    if current_price > overall_high:
        return "above range"
    # Express as quartile
    span = overall_high - overall_low
    if span == 0:
        return "at range"
    pct = (current_price - overall_low) / span
    if pct < 0.25:
        return "low end of range"
    if pct < 0.50:
        return "below median of range"
    if pct < 0.75:
        return "above median of range"
    return "high end of range"


def _build_markdown_table(
    methodologies: list[dict[str, Any]], currency: str
) -> str:
    header = (
        f"| Methodology | Low ({currency}) | Median ({currency}) | High ({currency}) |"
    )
    separator = "|---|---|---|---|"
    rows = []
    for m in methodologies:
        low = f"{m['low']:.2f}" if m.get("low") is not None else "—"
        med = f"{m['median']:.2f}" if m.get("median") is not None else "—"
        high = f"{m['high']:.2f}" if m.get("high") is not None else "—"
        rows.append(f"| {m['name']} | {low} | {med} | {high} |")
    return "\n".join([header, separator, *rows])


def _build_plotly_json(
    methodologies: list[dict[str, Any]],
    current_price: float,
    consensus_target_price: float | None,
    currency: str,
    title: str,
) -> str:
    """Build a Plotly JSON string for a football-field horizontal bar chart."""
    try:
        import plotly.graph_objects as go  # type: ignore[import-untyped]

        fig = go.Figure()

        # Sort methodologies by median (ascending) for chart readability
        sorted_methods = sorted(
            [m for m in methodologies if m.get("low") is not None],
            key=lambda m: m.get("median") or m.get("low") or 0,
        )
        names = [m["name"] for m in sorted_methods]

        for m in sorted_methods:
            low = float(m["low"])
            high = float(m["high"])
            median = float(m["median"]) if m.get("median") is not None else (low + high) / 2.0
            # Draw bar spanning [low, high]
            fig.add_trace(
                go.Bar(
                    name=m["name"],
                    y=[m["name"]],
                    x=[high - low],
                    base=[low],
                    orientation="h",
                    marker_color="steelblue",
                    opacity=0.7,
                    showlegend=False,
                    hovertemplate=(
                        f"{m['name']}<br>"
                        f"Low: {low:.2f}<br>"
                        f"Median: {median:.2f}<br>"
                        f"High: {high:.2f}<extra></extra>"
                    ),
                )
            )
            # Median tick
            fig.add_trace(
                go.Scatter(
                    x=[median],
                    y=[m["name"]],
                    mode="markers",
                    marker={"symbol": "line-ns", "size": 14, "color": "navy", "line": {"width": 2}},
                    showlegend=False,
                    hovertemplate=f"Median: {median:.2f}<extra></extra>",
                )
            )

        # Current price vertical line
        fig.add_vline(
            x=current_price,
            line_dash="solid",
            line_color="firebrick",
            line_width=2,
            annotation_text=f"Current ${current_price:.2f}",
            annotation_position="top right",
        )

        # Consensus target (dashed)
        if consensus_target_price is not None:
            fig.add_vline(
                x=consensus_target_price,
                line_dash="dash",
                line_color="darkorange",
                line_width=2,
                annotation_text=f"Consensus ${consensus_target_price:.2f}",
                annotation_position="top left",
            )

        fig.update_layout(
            title=title,
            xaxis_title=f"Price ({currency})",
            yaxis={"categoryorder": "array", "categoryarray": names},
            barmode="overlay",
            margin={"l": 180, "r": 40, "t": 60, "b": 60},
            height=max(300, 60 + 50 * len(names)),
        )

        return fig.to_json()

    except ImportError:
        # Plotly not installed — emit minimal valid JSON so tests can parse it
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
    methodologies: list[dict[str, Any]],
    current_price: float,
    consensus_target_price: float | None = None,
    currency: str = "USD",
    title: str = "Football Field Valuation Chart",
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Render a football-field valuation chart.

    Args:
        methodologies: List of dicts, each with:
            - name (str): methodology label.
            - low (float): low end of valuation range.
            - median (float | None): midpoint estimate.
            - high (float): high end of valuation range.
            - source_artifact_id (str | None): provenance.
        current_price: Current market price (drawn as vertical line).
        consensus_target_price: Optional consensus target (drawn as dashed line).
        currency: Currency symbol shown on x-axis label.
        title: Chart title.
        data_as_of: ISO date for computation.
        source_provenance: Upstream citation IDs.

    Returns:
        dict with chart_type, plotly_json, markdown_table, methodologies_summary,
        current_price_position, median_of_medians, verdict, warnings.
    """
    if not methodologies:
        raise ValueError("methodologies must be non-empty.")
    if current_price <= 0:
        raise ValueError(f"current_price must be positive; got {current_price}.")

    warnings: list[str] = []

    # Validate each methodology
    for i, m in enumerate(methodologies):
        if "name" not in m:
            raise ValueError(f"Methodology {i}: missing 'name'.")
        if "low" not in m or "high" not in m:
            raise ValueError(f"Methodology {m.get('name', i)!r}: missing 'low' or 'high'.")
        if m["low"] > m["high"]:
            warnings.append(
                f"Methodology {m['name']!r}: low ({m['low']}) > high ({m['high']}). "
                "Check inputs."
            )

    mom = _median_of_medians(methodologies)
    pos = _current_price_position(current_price, methodologies)

    # Verdict
    if mom is not None:
        gap_pct = (mom - current_price) / current_price
        if gap_pct > 0.10:
            verdict = (
                f"Undervalued vs. methodology median; "
                f"median of medians ${mom:.2f} is {gap_pct:+.1%} above current."
            )
        elif gap_pct < -0.10:
            verdict = (
                f"Overvalued vs. methodology median; "
                f"median of medians ${mom:.2f} is {gap_pct:+.1%} below current."
            )
        else:
            verdict = f"Trading near median of all methodologies (${mom:.2f})."
    else:
        verdict = "Insufficient data to compute median of medians."

    plotly_json = _build_plotly_json(
        methodologies, current_price, consensus_target_price, currency, title
    )
    markdown_table = _build_markdown_table(methodologies, currency)

    methodologies_summary = [
        {
            "name": m["name"],
            "low": m.get("low"),
            "median": m.get("median"),
            "high": m.get("high"),
            "source_artifact_id": m.get("source_artifact_id"),
        }
        for m in methodologies
    ]

    return {
        "chart_type": "football_field",
        "plotly_json": plotly_json,
        "markdown_table": markdown_table,
        "methodologies_summary": methodologies_summary,
        "current_price": current_price,
        "current_price_position": pos,
        "consensus_target_price": consensus_target_price,
        "median_of_medians": round(mom, 4) if mom is not None else None,
        "verdict": verdict,
        "currency": currency,
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
        name="football_field_chart",
        category=Category.DECISION,
        one_liner="Football-field chart: valuation ranges per methodology with current-price line.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Render a football-field valuation synthesis chart: horizontal bars showing the "
            "[low, high] range for each methodology (DCF, comps, DDM, SOTP), a median tick, "
            "and a current-price vertical line. Also produces a markdown table."
        ),
        when_to_use=[
            "Valuation synthesis section of an initiation or update report.",
            "When multiple valuation methodologies have been run and ranges are available.",
            "As the visual companion to price_target_blender.",
        ],
        when_not_to_use=[
            "When only one methodology is available — a single bar is not informative.",
            "For time-series charts — use chart_builder instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "methodologies": HelperParam(
                type="list[dict]",
                description=(
                    "List of {name, low, median, high, source_artifact_id} dicts. "
                    "Each dict represents one valuation methodology range."
                ),
                required=True,
            ),
            "current_price": HelperParam(
                type="float",
                description="Current market price; drawn as a vertical line.",
                required=True,
            ),
            "consensus_target_price": HelperParam(
                type="float",
                default=None,
                description="Optional consensus target; drawn as a dashed vertical line.",
                required=False,
            ),
            "currency": HelperParam(
                type="str",
                default="USD",
                description="Currency label shown on x-axis.",
                required=False,
            ),
            "title": HelperParam(
                type="str",
                default="Football Field Valuation Chart",
                description="Chart title.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="football_field_chart_output",
                type="football_field_chart_output",
                description=(
                    "chart_type, plotly_json, markdown_table, methodologies_summary, "
                    "current_price_position, median_of_medians, verdict."
                ),
            ),
        ],
        produces_artifacts=["football_field_chart_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.ARTIFACT_MISSING,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
