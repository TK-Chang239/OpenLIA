"""tornado_diagram — single-variable sensitivity sorted by impact magnitude.

Registered name: "tornado_diagram"

Varies each input independently (low vs. high) holding all others constant,
computes the output change, sorts by impact magnitude descending, and emits
a Plotly HTML horizontal bar chart + markdown table.

Design ref: planning/2026-05-21-equity-research-helpers-design.md §3.3
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Callable
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


def _compute_tornado(
    base_fn: Callable[..., float],
    base_kwargs: dict[str, Any],
    variables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Vary each variable independently; return sorted results.

    Args:
        base_fn: Callable(**base_kwargs) -> float.
        base_kwargs: Base parameter set passed to base_fn.
        variables: List of {name, low, high} dicts.

    Returns:
        List of {var_name, base_value, low_value, high_value,
                 impact_low, impact_high, impact_magnitude} sorted descending.
    """
    base_value = base_fn(**base_kwargs)
    results = []
    for var in variables:
        name = var["name"]
        low = var["low"]
        high = var["high"]

        # Low scenario
        low_kwargs = {**base_kwargs, name: low}
        low_value = base_fn(**low_kwargs)

        # High scenario
        high_kwargs = {**base_kwargs, name: high}
        high_value = base_fn(**high_kwargs)

        impact_low = low_value - base_value
        impact_high = high_value - base_value
        impact_magnitude = abs(impact_high - impact_low)

        results.append(
            {
                "var_name": name,
                "base_value": base_value,
                "low_input": low,
                "high_input": high,
                "low_value": low_value,
                "high_value": high_value,
                "impact_low": impact_low,
                "impact_high": impact_high,
                "impact_magnitude": impact_magnitude,
            }
        )

    results.sort(key=lambda r: r["impact_magnitude"], reverse=True)
    return results


def _build_markdown_table(results: list[dict[str, Any]], base_value: float) -> str:
    header = "| Variable | Low Input | High Input | Low Value | High Value | Impact Range |"
    separator = "|---|---|---|---|---|---|"
    rows = []
    for r in results:
        rows.append(
            f"| {r['var_name']} | {r['low_input']:.4f} | {r['high_input']:.4f} | "
            f"{r['low_value']:.2f} | {r['high_value']:.2f} | "
            f"{r['impact_low']:+.2f} to {r['impact_high']:+.2f} |"
        )
    return "\n".join([f"Base value: {base_value:.2f}", "", header, separator, *rows])


def _build_plotly_html(
    results: list[dict[str, Any]],
    base_value: float,
    title: str = "Tornado Diagram",
) -> str:
    try:
        import plotly.graph_objects as go  # type: ignore[import-untyped]

        var_names = [r["var_name"] for r in results]
        low_deltas = [r["impact_low"] for r in results]
        high_deltas = [r["impact_high"] for r in results]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                name="Low scenario",
                y=var_names,
                x=low_deltas,
                orientation="h",
                marker_color="indianred",
            )
        )
        fig.add_trace(
            go.Bar(
                name="High scenario",
                y=var_names,
                x=high_deltas,
                orientation="h",
                marker_color="seagreen",
            )
        )
        fig.update_layout(
            title=title,
            barmode="overlay",
            xaxis_title=f"Change from base ({base_value:.2f})",
            yaxis={"categoryorder": "total ascending"},
            margin={"l": 120, "r": 20, "t": 50, "b": 50},
        )
        return fig.to_json()
    except ImportError:
        return json.dumps({"error": "plotly not installed"})


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    base_fn: Callable[..., float] | None = None,
    base_kwargs: dict[str, Any] | None = None,
    variables: list[dict[str, Any]],
    title: str = "Tornado Diagram",
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    # pre-computed results (for callers that already computed values)
    precomputed_results: list[dict[str, Any]] | None = None,
    precomputed_base_value: float | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute and render a tornado sensitivity diagram.

    Either provide:
      - base_fn + base_kwargs: callable and its base parameter dict, OR
      - precomputed_results + precomputed_base_value.

    Args:
        base_fn: Callable(**kwargs) -> float.
        base_kwargs: Base parameter dict.
        variables: List of {name, low, high} dicts defining each variable's range.
        title: Chart title.
        precomputed_results: Pre-computed list (alternative to base_fn).
        precomputed_base_value: Base output value when using precomputed_results.
    """
    if not variables:
        raise ValueError("variables must be non-empty")
    for v in variables:
        if "name" not in v or "low" not in v or "high" not in v:
            raise ValueError(f"Each variable must have name/low/high, got: {v}")
        if v["low"] >= v["high"]:
            raise ValueError(
                f"Variable {v['name']!r}: low ({v['low']}) must be < high ({v['high']})"
            )

    if precomputed_results is not None:
        if precomputed_base_value is None:
            raise ValueError("precomputed_base_value required when precomputed_results provided")
        results = sorted(precomputed_results, key=lambda r: r["impact_magnitude"], reverse=True)
        base_value = precomputed_base_value
    elif base_fn is not None and base_kwargs is not None:
        results = _compute_tornado(base_fn, base_kwargs, variables)
        base_value = results[0]["base_value"] if results else 0.0
    else:
        raise ValueError(
            "Either base_fn+base_kwargs or precomputed_results+precomputed_base_value required"
        )

    markdown = _build_markdown_table(results, base_value)
    plotly_html = _build_plotly_html(results, base_value, title)

    return {
        "base_value": base_value,
        "results": results,
        "top_driver": results[0]["var_name"] if results else None,
        "markdown_table": markdown,
        "html": plotly_html,
        "title": title,
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
        name="tornado_diagram",
        category=Category.DCF,
        one_liner=(
            "Single-variable sensitivity ranked by impact magnitude; "
            "Plotly horizontal bar chart + markdown table."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Rank which assumptions drive valuation the most by varying each "
            "input independently between a low and high bound. Sorted by impact "
            "magnitude descending. Primary use: DCF driver prioritization."
        ),
        when_to_use=[
            "When you need to rank which assumptions matter most for a DCF or other model.",
            "After sensitivity_table to understand which axis dominates.",
        ],
        when_not_to_use=[
            "2-variable joint sensitivity — use sensitivity_table.",
            "Probability-weighted scenarios — use scenario_weighting.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "variables": HelperParam(
                type="list[dict]",
                description="List of {name, low, high} dicts. Each variable is swept independently.",  # noqa: E501
                required=True,
            ),
            "base_fn": HelperParam(
                type="Callable",
                default=None,
                description="Function(**base_kwargs) -> float to evaluate.",
                required=False,
            ),
            "base_kwargs": HelperParam(
                type="dict",
                default=None,
                description="Base parameter dict for base_fn.",
                required=False,
            ),
            "precomputed_results": HelperParam(
                type="list[dict]",
                default=None,
                description="Pre-computed results (alternative to base_fn).",
                required=False,
            ),
            "precomputed_base_value": HelperParam(
                type="float",
                default=None,
                description="Base output value when using precomputed_results.",
                required=False,
            ),
            "title": HelperParam(
                type="str",
                default="Tornado Diagram",
                description="Chart title.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="tornado_diagram_output",
                type="tornado_diagram_output",
                description="Ranked results, markdown table, and Plotly HTML bar chart.",
            ),
        ],
        produces_artifacts=["tornado_diagram_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
