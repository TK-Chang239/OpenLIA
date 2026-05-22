"""ft_capital_structure — debt mix, WACC inputs, and capital structure metrics."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.solvency_model as _solv

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
    total_debt: float,
    total_equity: float,
    total_assets: float,
    interest_expense: float,
    income_tax_rate: float = 0.21,
    market_cap: float = 0.0,
    risk_free_rate: float = 0.043,
    equity_risk_premium: float = 0.055,
    beta: float = 1.0,
    net_income: float = 0.0,
    ebit: float = 0.0,
    depreciation_and_amortization: float = 0.0,
    preferred_equity: float = 0.0,
    preferred_dividend_rate: float = 0.0,
    short_term_debt: float = 0.0,
    long_term_debt: float = 0.0,
) -> dict[str, Any]:
    """Compute capital structure metrics and WACC inputs.

    WACC = (E/V) * Re + (D/V) * Rd * (1 - T)
    where:
        E = market value of equity (market_cap)
        D = market value of debt (total_debt)
        V = E + D
        Re = cost of equity (CAPM: Rf + beta * ERP)
        Rd = cost of debt (interest_expense / total_debt)
        T  = tax rate
    """
    debt_to_equity = float(_solv.get_debt_to_equity_ratio(total_debt, total_equity))
    debt_to_assets = float(_solv.get_debt_to_assets_ratio(total_debt, total_assets))
    equity_multiplier = float(_solv.get_equity_multiplier(total_assets, total_equity))

    # Cost of debt (pre-tax)
    cost_of_debt_pretax = interest_expense / total_debt if total_debt != 0 else None
    cost_of_debt_aftertax = (
        cost_of_debt_pretax * (1 - income_tax_rate) if cost_of_debt_pretax is not None else None
    )

    # Cost of equity via CAPM
    cost_of_equity = risk_free_rate + beta * equity_risk_premium

    # WACC (using market cap if provided, else book equity)
    equity_value = market_cap if market_cap != 0 else total_equity
    total_capital = equity_value + total_debt

    wacc: float | None = None
    if total_capital != 0 and cost_of_debt_aftertax is not None:
        equity_weight = equity_value / total_capital
        debt_weight = total_debt / total_capital
        wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt_aftertax

    # Debt mix
    short_term_pct = short_term_debt / total_debt if total_debt != 0 else None
    long_term_pct = long_term_debt / total_debt if total_debt != 0 else None

    # Interest coverage
    interest_coverage: float | None = None
    if interest_expense != 0 and ebit != 0:
        interest_coverage = float(
            _solv.get_interest_coverage_ratio(ebit, depreciation_and_amortization, interest_expense)
        )

    return {
        "debt_to_equity": debt_to_equity,
        "debt_to_assets": debt_to_assets,
        "equity_multiplier": equity_multiplier,
        "cost_of_equity_capm": cost_of_equity,
        "cost_of_debt_pretax": cost_of_debt_pretax,
        "cost_of_debt_aftertax": cost_of_debt_aftertax,
        "wacc": wacc,
        "equity_weight": equity_value / total_capital if total_capital != 0 else None,
        "debt_weight": total_debt / total_capital if total_capital != 0 else None,
        "short_term_debt_pct": short_term_pct,
        "long_term_debt_pct": long_term_pct,
        "interest_coverage": interest_coverage,
        "income_tax_rate_used": income_tax_rate,
        "beta_used": beta,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_capital_structure",
        category=Category.BUSINESS_QUALITY,
        one_liner="Debt mix, WACC inputs (CAPM cost of equity + cost of debt), and leverage.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute capital structure metrics including WACC, cost of equity via CAPM, "
            "cost of debt, and debt/equity mix from balance sheet and income statement scalars."
        ),
        when_to_use=[
            "Generating WACC for a DCF model or equity research report.",
            "Analyzing debt structure and leverage for credit or equity analysis.",
        ],
        when_not_to_use=[
            "Full DCF valuation — use dcf_valuation which handles WACC internally.",
            "Simple D/E and interest coverage without WACC — use ft_solvency_ratios.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "total_debt": HelperParam(
                type="float", required=True, description="Total debt (short + long term)."
            ),
            "total_equity": HelperParam(
                type="float", required=True, description="Total shareholder equity (book value)."
            ),
            "total_assets": HelperParam(type="float", required=True, description="Total assets."),
            "interest_expense": HelperParam(
                type="float", required=True, description="Interest expense."
            ),
            "income_tax_rate": HelperParam(
                type="float",
                required=False,
                default=0.21,
                description="Effective income tax rate (decimal). Default 0.21.",
            ),
            "market_cap": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description=(
                    "Market cap. Used for equity weight in WACC. Falls back to book equity if 0."
                ),
            ),
            "risk_free_rate": HelperParam(
                type="float",
                required=False,
                default=0.043,
                description="Risk-free rate (decimal). Default 4.3% (10Y UST).",
            ),
            "equity_risk_premium": HelperParam(
                type="float",
                required=False,
                default=0.055,
                description="Equity risk premium (decimal). Default 5.5%.",
            ),
            "beta": HelperParam(
                type="float", required=False, default=1.0, description="Equity beta. Default 1.0."
            ),
            "net_income": HelperParam(
                type="float", required=False, default=0.0, description="Net income."
            ),
            "ebit": HelperParam(
                type="float", required=False, default=0.0, description="EBIT for interest coverage."
            ),
            "depreciation_and_amortization": HelperParam(
                type="float", required=False, default=0.0, description="D&A for interest coverage."
            ),
            "preferred_equity": HelperParam(
                type="float", required=False, default=0.0, description="Preferred equity."
            ),
            "preferred_dividend_rate": HelperParam(
                type="float", required=False, default=0.0, description="Preferred dividend rate."
            ),
            "short_term_debt": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Short-term debt for debt mix breakdown.",
            ),
            "long_term_debt": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Long-term debt for debt mix breakdown.",
            ),
        },
        outputs=[
            HelperOutput(
                name="capital_structure",
                type="dict",
                description=(
                    "Dict with debt_to_equity, debt_to_assets, equity_multiplier, "
                    "cost_of_equity_capm, cost_of_debt_pretax, cost_of_debt_aftertax, "
                    "wacc, equity_weight, debt_weight, short_term_debt_pct, "
                    "long_term_debt_pct, interest_coverage."
                ),
            ),
        ],
        produces_artifacts=["ft_capital_structure_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
