"""sbc_intensity — SBC/revenue, SBC/market cap, SBC/op income; dilution impact.

Registered name: "sbc_intensity"
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
    sbc: float,
    revenue: float,
    market_cap: float,
    operating_income: float | None = None,
    shares_outstanding: float | None = None,
    shares_outstanding_prior: float | None = None,
) -> dict[str, Any]:
    """Compute SBC intensity metrics.

    Args:
        sbc: Stock-based compensation for the period.
        revenue: Total revenue for the period.
        market_cap: Current market capitalization.
        operating_income: Optional operating income (for SBC/op income ratio).
        shares_outstanding: Optional current shares (for dilution rate).
        shares_outstanding_prior: Optional prior shares (for dilution rate).

    Returns:
        Dict with SBC intensity ratios and dilution metrics.
    """
    if revenue <= 0:
        raise ValueError("revenue must be positive")
    if market_cap <= 0:
        raise ValueError("market_cap must be positive")

    sbc_pct_revenue = sbc / revenue * 100.0
    sbc_pct_mktcap = sbc / market_cap * 100.0

    sbc_pct_op_income: float | None = None
    if operating_income is not None and operating_income != 0:
        sbc_pct_op_income = sbc / abs(operating_income) * 100.0

    # Net dilution from SBC (bps/year)
    dilution_bps: float | None = None
    if shares_outstanding is not None and shares_outstanding_prior is not None:
        if shares_outstanding_prior > 0:
            dilution_rate = (
                shares_outstanding - shares_outstanding_prior
            ) / shares_outstanding_prior
            dilution_bps = round(dilution_rate * 10000.0, 1)

    # Verdict
    if sbc_pct_revenue > 10.0:
        verdict = "high"
    elif sbc_pct_revenue > 5.0:
        verdict = "elevated"
    elif sbc_pct_revenue > 2.0:
        verdict = "moderate"
    else:
        verdict = "low"

    return {
        "sbc": sbc,
        "revenue": revenue,
        "market_cap": market_cap,
        "sbc_pct_revenue": round(sbc_pct_revenue, 2),
        "sbc_pct_market_cap": round(sbc_pct_mktcap, 2),
        "sbc_pct_operating_income": round(sbc_pct_op_income, 2)
        if sbc_pct_op_income is not None
        else None,
        "dilution_bps_per_year": dilution_bps,
        "verdict": verdict,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="sbc_intensity",
        category=Category.BUSINESS_QUALITY,
        one_liner="SBC/revenue, SBC/market cap, SBC/op income; net dilution bps/year.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Measure stock-based compensation as % of revenue, market cap, and operating income. "
            "Computes net dilution rate in basis points per year."
        ),
        when_to_use=[
            "Assessing SBC burden in high-compensation tech or early-stage companies.",
            "Feeding SBC intensity into forensic_panel.",
        ],
        when_not_to_use=[
            "Full cap table dilution history — use cap_table_dilution.",
            "Total shareholder yield — use total_shareholder_yield.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "sbc": HelperParam(
                type="float", required=True, description="Stock-based compensation."
            ),
            "revenue": HelperParam(type="float", required=True, description="Total revenue."),
            "market_cap": HelperParam(
                type="float", required=True, description="Market capitalization."
            ),
            "operating_income": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Operating income for SBC/op income ratio.",
            ),
            "shares_outstanding": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Current shares outstanding for dilution rate.",
            ),
            "shares_outstanding_prior": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Prior period shares for dilution rate.",
            ),
        },
        outputs=[
            HelperOutput(
                name="sbc_intensity",
                type="dict",
                description=(
                    "sbc_pct_revenue, sbc_pct_market_cap, sbc_pct_operating_income, "
                    "dilution_bps_per_year, verdict."
                ),
            ),
        ],
        produces_artifacts=["sbc_intensity_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
