"""ft_per_share_metrics — EPS, BVPS, FCFPS, DPS via FinanceToolkit."""

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
    net_income: float,
    total_equity: float,
    shares_outstanding: float,
    free_cash_flow: float = 0.0,
    dividends_paid: float = 0.0,
    operating_cash_flow: float = 0.0,
    total_revenue: float = 0.0,
    preferred_dividends: float = 0.0,
    preferred_equity: float = 0.0,
    capital_expenditure: float = 0.0,
    interest_expense: float = 0.0,
    interest_debt: float = 0.0,
) -> dict[str, Any]:
    """Compute per-share metrics from income statement, balance sheet, and cash flow inputs."""
    if shares_outstanding == 0:
        raise ValueError("shares_outstanding must be non-zero")

    eps = float(_val.get_earnings_per_share(net_income, preferred_dividends, shares_outstanding))
    bvps = float(_val.get_book_value_per_share(total_equity, preferred_equity, shares_outstanding))

    fcf_per_share: float | None = None
    if free_cash_flow != 0:
        fcf_per_share = free_cash_flow / shares_outstanding

    dps: float | None = None
    if dividends_paid != 0:
        dps = dividends_paid / shares_outstanding

    ocf_per_share: float | None = None
    if operating_cash_flow != 0:
        ocf_per_share = operating_cash_flow / shares_outstanding

    revenue_per_share: float | None = None
    if total_revenue != 0:
        revenue_per_share = float(_val.get_revenue_per_share(total_revenue, shares_outstanding))

    capex_per_share: float | None = None
    if capital_expenditure != 0:
        capex_per_share = float(_val.get_capex_per_share(capital_expenditure, shares_outstanding))

    interest_debt_per_share: float | None = None
    if interest_debt != 0:
        interest_debt_per_share = float(
            _val.get_interest_debt_per_share(interest_debt, shares_outstanding)
        )

    return {
        "eps": eps,
        "book_value_per_share": bvps,
        "free_cash_flow_per_share": fcf_per_share,
        "dividends_per_share": dps,
        "operating_cash_flow_per_share": ocf_per_share,
        "revenue_per_share": revenue_per_share,
        "capex_per_share": capex_per_share,
        "interest_debt_per_share": interest_debt_per_share,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_per_share_metrics",
        category=Category.BUSINESS_QUALITY,
        one_liner="EPS, BVPS, FCFPS, DPS, and other per-share metrics.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute per-share financial metrics using FinanceToolkit valuation model "
            "functions applied to user-supplied income statement, balance sheet, and "
            "cash flow scalars."
        ),
        when_to_use=[
            "Computing per-share metrics for an equity research report.",
            "Feeding EPS and BVPS into valuation ratio calculations.",
        ],
        when_not_to_use=[
            "Market multiples (P/E, P/B) — use ft_valuation_ratios.",
            "Dividend-specific analysis — use ft_dividend_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "net_income": HelperParam(type="float", required=True, description="Net income."),
            "total_equity": HelperParam(
                type="float", required=True, description="Total shareholder equity."
            ),
            "shares_outstanding": HelperParam(
                type="float", required=True, description="Diluted shares outstanding."
            ),
            "free_cash_flow": HelperParam(
                type="float", required=False, default=0.0, description="Free cash flow."
            ),
            "dividends_paid": HelperParam(
                type="float", required=False, default=0.0, description="Total dividends paid."
            ),
            "operating_cash_flow": HelperParam(
                type="float", required=False, default=0.0, description="Operating cash flow."
            ),
            "total_revenue": HelperParam(
                type="float", required=False, default=0.0, description="Total revenue."
            ),
            "preferred_dividends": HelperParam(
                type="float", required=False, default=0.0, description="Preferred dividends paid."
            ),
            "preferred_equity": HelperParam(
                type="float", required=False, default=0.0, description="Preferred equity."
            ),
            "capital_expenditure": HelperParam(
                type="float", required=False, default=0.0, description="Capital expenditure."
            ),
            "interest_debt": HelperParam(
                type="float", required=False, default=0.0, description="Interest-bearing debt."
            ),
        },
        outputs=[
            HelperOutput(
                name="per_share_metrics",
                type="dict",
                description=(
                    "Dict with eps, book_value_per_share, free_cash_flow_per_share, "
                    "dividends_per_share, operating_cash_flow_per_share, revenue_per_share, "
                    "capex_per_share, interest_debt_per_share."
                ),
            ),
        ],
        produces_artifacts=["ft_per_share_metrics_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
