"""sustainable_growth_rate — SGR = ROE * (1 - payout_ratio).

Registered name: "sustainable_growth_rate"
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper


def execute(
    roe: float,
    payout_ratio: float,
    actual_revenue_growth: float | None = None,
) -> dict[str, Any]:
    """Compute Sustainable Growth Rate.

    SGR = ROE * (1 - payout_ratio)
    SGR represents the maximum growth rate a firm can sustain without external financing.

    Args:
        roe: Return on Equity as decimal (e.g. 0.20 for 20%).
        payout_ratio: Dividend payout ratio as decimal (e.g. 0.30 for 30%).
            Must be in [0, 1].
        actual_revenue_growth: Optional actual revenue growth rate for comparison.

    Returns:
        Dict with SGR, retention_ratio, and optional gap analysis.
    """
    if not (0.0 <= payout_ratio <= 1.0):
        raise ValueError(f"payout_ratio must be in [0, 1], got {payout_ratio}")

    retention_ratio = 1.0 - payout_ratio
    sgr = roe * retention_ratio

    # Gap analysis
    growth_gap: float | None = None
    gap_verdict: str | None = None
    if actual_revenue_growth is not None:
        growth_gap = actual_revenue_growth - sgr
        if growth_gap > 0.02:  # growing > 2ppt above SGR
            gap_verdict = "unsustainable_high"
        elif growth_gap < -0.02:
            gap_verdict = "growing_below_potential"
        else:
            gap_verdict = "sustainable"

    return {
        "roe": round(roe, 4),
        "payout_ratio": round(payout_ratio, 4),
        "retention_ratio": round(retention_ratio, 4),
        "sustainable_growth_rate": round(sgr, 4),
        "sgr_pct": round(sgr * 100.0, 2),
        "actual_revenue_growth": actual_revenue_growth,
        "growth_gap": round(growth_gap, 4) if growth_gap is not None else None,
        "gap_verdict": gap_verdict,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="sustainable_growth_rate",
        category=Category.BUSINESS_QUALITY,
        one_liner="SGR = ROE * (1 - payout_ratio); gap vs actual growth.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the Sustainable Growth Rate: the maximum growth rate a company can "
            "sustain without external financing. Compare to actual growth to flag unsustainable "
            "expansion or underutilized potential."
        ),
        when_to_use=[
            "Growth sustainability assessment in equity research.",
            "Flagging companies growing faster than internally sustainable.",
        ],
        when_not_to_use=[
            "ROE derivation — compute ROE externally before calling this helper.",
            "Dividend sustainability — use ft_dividend_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "roe": HelperParam(
                type="float",
                required=True,
                description="Return on Equity as decimal (e.g. 0.20 for 20%).",
            ),
            "payout_ratio": HelperParam(
                type="float",
                required=True,
                description="Dividend payout ratio as decimal in [0, 1].",
            ),
            "actual_revenue_growth": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Actual revenue growth rate for gap analysis.",
            ),
        },
        outputs=[
            HelperOutput(
                name="sustainable_growth_rate",
                type="dict",
                description=(
                    "roe, payout_ratio, retention_ratio, sustainable_growth_rate, "
                    "sgr_pct, growth_gap, gap_verdict."
                ),
            ),
        ],
        produces_artifacts=["sustainable_growth_rate_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
