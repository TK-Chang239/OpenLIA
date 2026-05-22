"""expected_total_return — capital return + dividend yield = ETR.

Registered name: "expected_total_return"

Combines the blended price target with the current price and forward dividend
yield to produce the expected total return (ETR) over a stated horizon.

Decision layer position: second helper. Takes price_target_blender output
(or any explicit price target) and feeds rating_band_assigner.

Design ref: planning/2026-05-22-helpers-design-supplement.md §7.2
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

_MAX_SANE_YIELD = 0.20  # 20% — warn above this
_MAX_HORIZON_MONTHS_FOR_ANNUALIZE = 24  # beyond this record both raw + annualized


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _capital_return(price_target: float, current_price: float) -> float:
    if current_price == 0:
        raise ValueError("current_price cannot be zero.")
    return price_target / current_price - 1.0


def _etr(capital_return: float, forward_dividend_yield: float, horizon_months: int) -> float:
    return capital_return + forward_dividend_yield * (horizon_months / 12.0)


def _annualized(total_return: float, horizon_months: int) -> float:
    if horizon_months <= 0:
        raise ValueError("horizon_months must be positive.")
    return (1.0 + total_return) ** (12.0 / horizon_months) - 1.0


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    price_target: float,
    current_price: float,
    forward_dividend_yield: float,
    horizon_months: int = 12,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute expected total return over a stated horizon.

    Args:
        price_target: Blended or analyst price target.
        current_price: Current market price.
        forward_dividend_yield: Forward annual dividend yield (decimal, e.g. 0.02).
        horizon_months: Return horizon in months (default 12).
        data_as_of: ISO date for the computation.
        source_provenance: Upstream citation IDs.

    Returns:
        dict with capital_return_pct, income_return_pct, expected_total_return_pct,
        annualized_etr_pct, horizon_months, warnings.
    """
    if current_price <= 0:
        raise ValueError(f"current_price must be positive; got {current_price}.")
    if horizon_months <= 0:
        raise ValueError(f"horizon_months must be positive; got {horizon_months}.")
    if forward_dividend_yield < 0:
        raise ValueError(
            f"forward_dividend_yield cannot be negative; got {forward_dividend_yield}."
        )

    warnings: list[str] = []

    if forward_dividend_yield > _MAX_SANE_YIELD:
        warnings.append(
            f"forward_dividend_yield {forward_dividend_yield:.1%} exceeds {_MAX_SANE_YIELD:.0%}. "
            "Verify input — this appears anomalously high."
        )

    cap_ret = _capital_return(price_target, current_price)
    income_ret = forward_dividend_yield * (horizon_months / 12.0)
    total_ret = cap_ret + income_ret
    ann_ret = _annualized(total_ret, horizon_months)

    if horizon_months > _MAX_HORIZON_MONTHS_FOR_ANNUALIZE:
        warnings.append(
            f"Horizon {horizon_months} months > 24. "
            "Annualized ETR smooths to a long-run figure; "
            "raw ETR and annualized ETR both reported."
        )

    return {
        "current_price": current_price,
        "price_target": price_target,
        "capital_return_pct": round(cap_ret, 6),
        "income_return_pct": round(income_ret, 6),
        "expected_total_return_pct": round(total_ret, 6),
        "annualized_etr_pct": round(ann_ret, 6),
        "horizon_months": horizon_months,
        "forward_dividend_yield": forward_dividend_yield,
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
        name="expected_total_return",
        category=Category.DECISION,
        one_liner="ETR = capital return from price target + dividend yield over horizon.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Combine a blended price target with the current price and forward dividend yield "
            "to produce expected total return (capital + income) over a stated investment horizon."
        ),
        when_to_use=[
            "After price_target_blender to quantify the ETR of the blended PT.",
            "As direct input to rating_band_assigner (ETR is one of two required inputs).",
            "When comparing total-return expectations across sectors with different yields.",
        ],
        when_not_to_use=[
            "When you only want capital gain — read capital_return_pct from the output.",
            "For multi-asset portfolio-level return expectations — out of scope.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "price_target": HelperParam(
                type="float",
                description="Blended or explicit analyst price target.",
                required=True,
            ),
            "current_price": HelperParam(
                type="float",
                description="Current market price (must be positive).",
                required=True,
            ),
            "forward_dividend_yield": HelperParam(
                type="float",
                description="Forward annual dividend yield as decimal (e.g. 0.02 = 2%).",
                required=True,
            ),
            "horizon_months": HelperParam(
                type="int",
                default=12,
                description="Investment horizon in months. Default 12.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="expected_total_return_output",
                type="expected_total_return_output",
                description=(
                    "capital_return_pct, income_return_pct, expected_total_return_pct, "
                    "annualized_etr_pct, horizon_months."
                ),
            ),
        ],
        produces_artifacts=["expected_total_return_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
