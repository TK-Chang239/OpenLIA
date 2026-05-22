"""scenario_weighting — probability-weighted scenario analysis.

Registered name: "scenario_weighting"

Accepts a list of (scenario_name, value, probability) tuples and computes
the probability-weighted central value plus a full breakdown.
Probabilities must sum to 1.0 (within tolerance).

Design ref: planning/2026-05-21-equity-research-helpers-design.md §3.4
"""

from __future__ import annotations

import datetime
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

_PROB_SUM_TOLERANCE = 0.005  # allow up to 0.5% rounding slack


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _weighted_value(scenarios: list[dict[str, Any]]) -> float:
    return sum(s["value"] * s["probability"] for s in scenarios)


def _prob_sum(scenarios: list[dict[str, Any]]) -> float:
    return sum(s["probability"] for s in scenarios)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    scenarios: list[dict[str, Any]],
    label: str = "value",
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute probability-weighted scenario analysis.

    Args:
        scenarios: List of dicts, each with:
            - name (str): scenario label, e.g. "base", "bull", "bear".
            - value (float): output value for this scenario.
            - probability (float): probability weight (decimal, e.g. 0.60).
        label: What 'value' represents (e.g. "equity_value_per_share").
        data_as_of: ISO date for freshness.
        source_provenance: Citation IDs.
    """
    if not scenarios:
        raise ValueError("scenarios must be non-empty")

    for i, s in enumerate(scenarios):
        if "name" not in s:
            raise ValueError(f"Scenario {i}: missing 'name'")
        if "value" not in s:
            raise ValueError(f"Scenario {i!r}: missing 'value'")
        if "probability" not in s:
            raise ValueError(f"Scenario {i!r}: missing 'probability'")
        p = s["probability"]
        if p < 0 or p > 1.0 + _PROB_SUM_TOLERANCE:
            raise ValueError(f"Scenario {s['name']!r}: probability {p} is outside [0, 1]")

    total_prob = _prob_sum(scenarios)
    if abs(total_prob - 1.0) > _PROB_SUM_TOLERANCE:
        raise ValueError(
            f"Scenario probabilities must sum to 1.0; got {total_prob:.4f}. "
            "Adjust probabilities so they sum exactly to 1.0."
        )

    weighted = _weighted_value(scenarios)

    breakdown = [
        {
            "name": s["name"],
            "value": s["value"],
            "probability": s["probability"],
            "weighted_contribution": s["value"] * s["probability"],
            "value_vs_weighted": s["value"] - weighted,
        }
        for s in scenarios
    ]

    # Summary stats
    values = [s["value"] for s in scenarios]
    min_val = min(values)
    max_val = max(values)
    value_range = max_val - min_val

    # Markdown table
    header = f"| Scenario | {label} | Probability | Weighted Contribution |"
    separator = "|---|---|---|---|"
    rows = [
        (
            f"| {b['name']} | {b['value']:.2f} | {b['probability']:.1%} "
            f"| {b['weighted_contribution']:.2f} |"
        )
        for b in breakdown
    ]
    footer = f"| **Weighted** | **{weighted:.2f}** | **{total_prob:.1%}** | **{weighted:.2f}** |"
    markdown_table = "\n".join([header, separator, *rows, footer])

    return {
        "weighted_value": weighted,
        "label": label,
        "scenario_count": len(scenarios),
        "scenario_breakdown": breakdown,
        "value_range": {"min": min_val, "max": max_val, "spread": value_range},
        "probabilities_sum": total_prob,
        "markdown_table": markdown_table,
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
        name="scenario_weighting",
        category=Category.DCF,
        one_liner="Probability-weighted scenario analysis: base/bull/bear or any named scenarios.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Combine multiple named scenarios (e.g., base/bull/bear) into a "
            "probability-weighted central value. Rejects probability sets that "
            "do not sum to 1.0. Emits a full breakdown per scenario."
        ),
        when_to_use=[
            "Scenario section of an initiation or update report.",
            "When the analyst has distinct outcomes with assigned probabilities.",
            "Pairing with DCF or DDM outputs to produce a blended price target.",
        ],
        when_not_to_use=[
            "2-variable joint sensitivity — use sensitivity_table.",
            "Ranked single-variable sweeps — use tornado_diagram.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "scenarios": HelperParam(
                type="list[dict]",
                description=(
                    "List of {name, value, probability} dicts. Probabilities must sum to 1.0."
                ),
                required=True,
            ),
            "label": HelperParam(
                type="str",
                default="value",
                description="Label for the value column (e.g. 'equity_value_per_share').",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="scenario_panel",
                type="scenario_panel",
                description=(
                    "Weighted value, scenario breakdown, value range, and markdown table."
                ),
            ),
        ],
        produces_artifacts=["scenario_panel"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
