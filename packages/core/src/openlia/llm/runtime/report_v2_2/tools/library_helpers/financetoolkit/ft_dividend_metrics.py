"""ft_dividend_metrics — payout ratio, dividend yield, dividend growth via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.valuation_model as _val

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
    dividends_paid: float,
    net_income: float,
    share_price: float,
    dividends_per_share: float = 0.0,
    dividends_paid_prior: float = 0.0,
    free_cash_flow: float = 0.0,
    operating_cash_flow: float = 0.0,
    shares_outstanding: float = 0.0,
) -> dict[str, Any]:
    """Compute dividend and payout metrics."""
    payout_ratio: float | None = None
    if net_income != 0:
        payout_ratio = float(_val.get_dividend_payout_ratio(dividends_paid, net_income))

    dps = dividends_per_share
    if dps == 0 and shares_outstanding != 0:
        dps = dividends_paid / shares_outstanding

    dividend_yield: float | None = None
    if dps != 0 and share_price != 0:
        dividend_yield = float(_val.get_dividend_yield(dps, share_price))

    dividend_growth: float | None = None
    if dividends_paid_prior != 0 and dividends_paid != 0:
        dividend_growth = (dividends_paid - dividends_paid_prior) / abs(dividends_paid_prior)

    # Dividend coverage by FCF
    fcf_payout: float | None = None
    if free_cash_flow != 0:
        fcf_payout = dividends_paid / free_cash_flow

    # Dividend coverage by OCF
    ocf_payout: float | None = None
    if operating_cash_flow != 0:
        ocf_payout = dividends_paid / operating_cash_flow

    # Retention ratio (plowback)
    retention_ratio: float | None = None
    if payout_ratio is not None:
        retention_ratio = 1.0 - payout_ratio

    return {
        "dividends_paid": dividends_paid,
        "dividends_per_share": dps if dps != 0 else None,
        "payout_ratio": payout_ratio,
        "dividend_yield": dividend_yield,
        "dividend_growth": dividend_growth,
        "fcf_payout_ratio": fcf_payout,
        "ocf_payout_ratio": ocf_payout,
        "retention_ratio": retention_ratio,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_dividend_metrics",
        category=Category.BUSINESS_QUALITY,
        one_liner="Payout ratio, dividend yield, growth, and FCF/OCF coverage.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute dividend sustainability and yield metrics using FinanceToolkit "
            "valuation model functions applied to user-supplied cash flow and income scalars."
        ),
        when_to_use=[
            "Assessing dividend sustainability in an equity research report.",
            "Computing dividend yield and payout ratio for income-focused analysis.",
        ],
        when_not_to_use=[
            "Broad per-share metrics — use ft_per_share_metrics.",
            "Companies that don't pay dividends — outputs will be mostly null.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "dividends_paid": HelperParam(
                type="float", required=True, description="Total dividends paid."
            ),
            "net_income": HelperParam(type="float", required=True, description="Net income."),
            "share_price": HelperParam(
                type="float", required=True, description="Current share price."
            ),
            "dividends_per_share": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Annual DPS. Computed from dividends_paid/shares_outstanding if 0.",
            ),
            "dividends_paid_prior": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Prior period dividends paid. Used for growth calculation.",
            ),
            "free_cash_flow": HelperParam(
                type="float", required=False, default=0.0, description="FCF for FCF payout ratio."
            ),
            "operating_cash_flow": HelperParam(
                type="float", required=False, default=0.0, description="OCF for OCF payout ratio."
            ),
            "shares_outstanding": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Shares outstanding. Used to compute DPS if dividends_per_share is 0.",
            ),
        },
        outputs=[
            HelperOutput(
                name="dividend_metrics",
                type="dict",
                description=(
                    "Dict with dividends_paid, dividends_per_share, payout_ratio, "
                    "dividend_yield, dividend_growth, fcf_payout_ratio, "
                    "ocf_payout_ratio, retention_ratio."
                ),
            ),
        ],
        produces_artifacts=["ft_dividend_metrics_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
