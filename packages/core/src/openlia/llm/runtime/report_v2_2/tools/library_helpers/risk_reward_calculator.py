"""risk_reward_calculator — asymmetric upside/downside ratio with probability weighting.

Registered name: "risk_reward_calculator"

Given bull and bear case prices (plus optional probabilities), computes the
upside/downside ratio, expected value, asymmetry score, and a verdict string.

Decision layer position: third helper. Output risk_reward_ratio feeds
rating_band_assigner.

Design ref: planning/2026-05-22-helpers-design-supplement.md §7.3
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

_VERY_FAVORABLE_THRESHOLD = 3.0
_FAVORABLE_THRESHOLD = 2.0
_POSITIVE_THRESHOLD = 1.5
_MARGINAL_THRESHOLD = 1.0


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _verdict(ratio: float | None) -> str:
    if ratio is None:
        return "undefined"
    if ratio >= _VERY_FAVORABLE_THRESHOLD:
        return "very favorable"
    if ratio >= _FAVORABLE_THRESHOLD:
        return "favorable"
    if ratio >= _POSITIVE_THRESHOLD:
        return "positive"
    if ratio >= _MARGINAL_THRESHOLD:
        return "marginal"
    return "unfavorable"


def _asymmetry_score(upside_pct: float, downside_pct: float) -> float:
    """Normalized asymmetry: +1 = all upside, -1 = all downside, 0 = symmetric."""
    total_mag = abs(upside_pct) + abs(downside_pct)
    if total_mag == 0:
        return 0.0
    return (abs(upside_pct) - abs(downside_pct)) / total_mag


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    current_price: float,
    bull_case_price: float,
    bear_case_price: float,
    bull_probability: float | None = None,
    bear_probability: float | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute asymmetric risk/reward profile.

    Args:
        current_price: Current market price.
        bull_case_price: Upside scenario target price.
        bear_case_price: Downside scenario target price.
        bull_probability: Probability of bull case (decimal). If supplied,
            bear_probability must also be supplied and sum to ≤ 1.0.
        bear_probability: Probability of bear case (decimal).
        data_as_of: ISO date for the computation.
        source_provenance: Upstream citation IDs.

    Returns:
        dict with upside_pct, downside_pct, risk_reward_ratio, expected_value,
        max_drawdown, asymmetry_score, verdict, warnings.
    """
    if current_price <= 0:
        raise ValueError(f"current_price must be positive; got {current_price}.")

    warnings: list[str] = []

    upside_pct = bull_case_price / current_price - 1.0
    downside_pct = bear_case_price / current_price - 1.0

    # Edge cases
    if bear_case_price >= current_price:
        warnings.append(
            "bear_case_price >= current_price: no downside identified. "
            "Risk/reward ratio undefined — check bear case rigor."
        )
    if bull_case_price <= current_price:
        warnings.append(
            "bull_case_price <= current_price: no upside identified."
        )

    # Risk/reward ratio
    if downside_pct == 0 or downside_pct > 0:
        ratio: float | None = None
    else:
        ratio = abs(upside_pct) / abs(downside_pct)

    # Expected value (probability-weighted)
    expected_value: float | None = None
    if bull_probability is not None and bear_probability is not None:
        if bull_probability < 0 or bear_probability < 0:
            raise ValueError("Probabilities must be non-negative.")
        if bull_probability + bear_probability > 1.0 + 1e-6:
            raise ValueError(
                f"bull_probability + bear_probability = "
                f"{bull_probability + bear_probability:.4f} > 1.0."
            )
        base_prob = 1.0 - bull_probability - bear_probability
        base_prob = max(base_prob, 0.0)
        # Base case price = current_price (conservative; caller can override by
        # providing only bull/bear that bracket a base case)
        expected_value = (
            bull_probability * bull_case_price
            + bear_probability * bear_case_price
            + base_prob * current_price
        )

    max_drawdown = downside_pct  # already negative (or 0)
    asymmetry = _asymmetry_score(upside_pct, downside_pct)
    verd = _verdict(ratio)

    # Narrative
    if ratio is not None:
        narrative = (
            f"{verd.capitalize()}: {ratio:.2f}x upside-to-downside; "
            f"bull case offers ${bull_case_price - current_price:+.2f} reward "
            f"vs ${bear_case_price - current_price:.2f} downside."
        )
    else:
        narrative = "Risk/reward ratio undefined — see warnings."

    return {
        "current_price": current_price,
        "bull_case": bull_case_price,
        "bear_case": bear_case_price,
        "upside_pct": round(upside_pct, 6),
        "downside_pct": round(downside_pct, 6),
        "risk_reward_ratio": round(ratio, 4) if ratio is not None else None,
        "expected_value": round(expected_value, 4) if expected_value is not None else None,
        "max_drawdown": round(max_drawdown, 6),
        "asymmetry_score": round(asymmetry, 4),
        "verdict": verd,
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
        name="risk_reward_calculator",
        category=Category.DECISION,
        one_liner="Upside/downside ratio, expected value, and verdict from bull/bear case prices.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the risk/reward profile from explicit bull and bear case prices, "
            "producing upside/downside percentages, an R/R ratio, optional probability-weighted "
            "expected value, and a verdict band."
        ),
        when_to_use=[
            "After scenario analysis (DCF or comparables) to quantify asymmetry.",
            "As input to rating_band_assigner (risk_reward_ratio is required).",
            "Whenever a report section needs explicit R/R framing.",
        ],
        when_not_to_use=[
            "For full scenario probability weighting — use scenario_weighting.",
            "For implied upside from a single PT — use implied_upside_downside.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "current_price": HelperParam(
                type="float",
                description="Current market price.",
                required=True,
            ),
            "bull_case_price": HelperParam(
                type="float",
                description="Bull-case target price.",
                required=True,
            ),
            "bear_case_price": HelperParam(
                type="float",
                description="Bear-case target price.",
                required=True,
            ),
            "bull_probability": HelperParam(
                type="float",
                default=None,
                description="Bull-case probability (decimal). Optional; enables expected_value.",
                required=False,
            ),
            "bear_probability": HelperParam(
                type="float",
                default=None,
                description="Bear-case probability (decimal). Required if bull_probability given.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="risk_reward_output",
                type="risk_reward_output",
                description=(
                    "upside_pct, downside_pct, risk_reward_ratio, expected_value, "
                    "max_drawdown, asymmetry_score, verdict, narrative."
                ),
            ),
        ],
        produces_artifacts=["risk_reward_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
