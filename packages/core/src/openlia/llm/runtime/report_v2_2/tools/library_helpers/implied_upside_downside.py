"""implied_upside_downside — implied upside/downside from PT + downside scenario.

Registered name: "implied_upside_downside"

Given a price target, a downside scenario value, and the current price, computes
implied upside %, implied downside %, R/R ratio, and breakeven probability.

Design ref: planning/2026-05-22-helpers-design-supplement.md §7.4
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

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _breakeven_probability(upside_pct: float, downside_pct: float) -> float | None:
    """Probability of hitting target such that EV = 0.

    P * upside + (1 - P) * downside = 0
    P = -downside / (upside - downside)
    """
    denom = upside_pct - downside_pct
    if denom == 0:
        return None
    p = -downside_pct / denom
    return max(0.0, min(1.0, p))


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    price_target: float,
    downside_scenario_value: float,
    current_price: float,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute implied upside/downside metrics from price target and downside scenario.

    Args:
        price_target: Analyst or blended price target (upside case).
        downside_scenario_value: Bear-case or downside scenario value.
        current_price: Current market price.
        data_as_of: ISO date for computation.
        source_provenance: Upstream citation IDs.

    Returns:
        dict with implied_upside_pct, implied_downside_pct, risk_reward_ratio,
        breakeven_probability, and narrative.
    """
    if current_price <= 0:
        raise ValueError(f"current_price must be positive; got {current_price}.")

    warnings: list[str] = []

    implied_upside_pct = price_target / current_price - 1.0
    implied_downside_pct = downside_scenario_value / current_price - 1.0

    if implied_upside_pct <= 0:
        warnings.append(
            f"price_target ${price_target:.2f} is at or below current_price ${current_price:.2f}. "
            "Implied upside is non-positive."
        )
    if implied_downside_pct >= 0:
        warnings.append(
            f"downside_scenario_value ${downside_scenario_value:.2f} is at or above "
            f"current_price ${current_price:.2f}. No downside scenario identified."
        )

    # R/R ratio
    if implied_downside_pct == 0 or implied_downside_pct > 0:
        rr_ratio: float | None = None
    else:
        rr_ratio = abs(implied_upside_pct) / abs(implied_downside_pct)

    breakeven_prob = _breakeven_probability(implied_upside_pct, implied_downside_pct)

    # Narrative
    if rr_ratio is not None and breakeven_prob is not None:
        narrative = (
            f"Implied upside {implied_upside_pct:+.1%} to PT ${price_target:.2f}; "
            f"implied downside {implied_downside_pct:+.1%} to bear ${downside_scenario_value:.2f}. "
            f"R/R {rr_ratio:.2f}x. Breakeven probability {breakeven_prob:.1%} "
            "(probability of reaching PT needed for zero expected return)."
        )
    else:
        narrative = "R/R ratio undefined — no downside identified."

    return {
        "price_target": price_target,
        "downside_scenario_value": downside_scenario_value,
        "current_price": current_price,
        "implied_upside_pct": round(implied_upside_pct, 6),
        "implied_downside_pct": round(implied_downside_pct, 6),
        "risk_reward_ratio": round(rr_ratio, 4) if rr_ratio is not None else None,
        "breakeven_probability": round(breakeven_prob, 4) if breakeven_prob is not None else None,
        "narrative": narrative,
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
        name="implied_upside_downside",
        category=Category.DECISION,
        one_liner="Implied upside/downside %, R/R ratio, and breakeven probability from PT + bear.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Derive implied upside percentage, implied downside percentage, risk/reward ratio, "
            "and breakeven probability from a price target and a downside scenario value."
        ),
        when_to_use=[
            "When you have a single PT and a bear-case target to triangulate.",
            "As a lightweight alternative to risk_reward_calculator when only two cases exist.",
            "To express the breakeven probability clearly in the investment thesis.",
        ],
        when_not_to_use=[
            "When you have three or more scenarios — "
            "use risk_reward_calculator or scenario_weighting.",
            "When probability weights for each case are available — use risk_reward_calculator.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "price_target": HelperParam(
                type="float",
                description="Analyst or blended price target (upside case).",
                required=True,
            ),
            "downside_scenario_value": HelperParam(
                type="float",
                description="Bear-case or downside scenario value.",
                required=True,
            ),
            "current_price": HelperParam(
                type="float",
                description="Current market price.",
                required=True,
            ),
        },
        outputs=[
            HelperOutput(
                name="implied_upside_downside_output",
                type="implied_upside_downside_output",
                description=(
                    "implied_upside_pct, implied_downside_pct, risk_reward_ratio, "
                    "breakeven_probability, narrative."
                ),
            ),
        ],
        produces_artifacts=["implied_upside_downside_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
