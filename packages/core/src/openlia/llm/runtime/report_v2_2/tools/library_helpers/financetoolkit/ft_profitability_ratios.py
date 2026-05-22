"""ft_profitability_ratios — gross/operating/net margin, ROA, ROE via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.profitability_model as _prof

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
    revenue: float,
    gross_profit: float,
    operating_income: float,
    net_income: float,
    total_assets: float,
    total_equity: float,
    ebit: float = 0.0,
    interest_expense: float = 0.0,
    income_before_tax: float = 0.0,
    income_tax_expense: float = 0.0,
    operating_cash_flow: float = 0.0,
    free_cash_flow: float = 0.0,
    total_debt: float = 0.0,
    dividends: float = 0.0,
) -> dict[str, Any]:
    """Compute profitability ratios from income statement and balance sheet inputs."""
    # get_gross_margin(revenue, cogs) = (revenue - cogs) / revenue
    # We receive gross_profit directly, so compute margin as gross_profit / revenue
    gross_margin = gross_profit / revenue if revenue != 0 else 0.0
    operating_margin = float(_prof.get_operating_margin(operating_income, revenue))
    net_margin = float(_prof.get_net_profit_margin(net_income, revenue))
    roa = float(_prof.get_return_on_assets(net_income, total_assets))
    roe = float(_prof.get_return_on_equity(net_income, total_equity))

    roic: float | None = None
    if (total_equity + total_debt) != 0:
        roic = float(
            _prof.get_return_on_invested_capital(net_income, dividends, total_equity, total_debt)
        )

    ebit_to_revenue: float | None = None
    if ebit != 0:
        ebit_to_revenue = float(_prof.get_EBIT_to_revenue(ebit, revenue))

    effective_tax_rate: float | None = None
    if income_before_tax != 0:
        effective_tax_rate = float(
            _prof.get_effective_tax_rate(income_tax_expense, income_before_tax)
        )

    income_quality: float | None = None
    if net_income != 0 and operating_cash_flow != 0:
        income_quality = float(_prof.get_income_quality_ratio(operating_cash_flow, net_income))

    fcf_to_ocf: float | None = None
    if operating_cash_flow != 0 and free_cash_flow != 0:
        fcf_to_ocf = float(
            _prof.get_free_cash_flow_operating_cash_flow_ratio(free_cash_flow, operating_cash_flow)
        )

    return {
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "roa": roa,
        "roe": roe,
        "roic": roic,
        "ebit_to_revenue": ebit_to_revenue,
        "effective_tax_rate": effective_tax_rate,
        "income_quality_ratio": income_quality,
        "fcf_to_ocf_ratio": fcf_to_ocf,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_profitability_ratios",
        category=Category.BUSINESS_QUALITY,
        one_liner="Gross/operating/net margins, ROA, ROE, and ROIC.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute profitability ratios using FinanceToolkit model functions applied "
            "to user-supplied income statement and balance sheet scalars."
        ),
        when_to_use=[
            "Measuring margin quality and returns for an equity research report.",
            "Benchmarking ROE/ROA/ROIC for peer comparison.",
        ],
        when_not_to_use=[
            "Liquidity analysis — use ft_liquidity_ratios.",
            "Leverage analysis — use ft_solvency_ratios.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "revenue": HelperParam(
                type="float",
                required=True,
                description="Total revenue.",
            ),
            "gross_profit": HelperParam(
                type="float",
                required=True,
                description="Gross profit.",
            ),
            "operating_income": HelperParam(
                type="float",
                required=True,
                description="Operating income.",
            ),
            "net_income": HelperParam(
                type="float",
                required=True,
                description="Net income.",
            ),
            "total_assets": HelperParam(
                type="float",
                required=True,
                description="Total assets (used as both beginning and ending for averages).",
            ),
            "total_equity": HelperParam(
                type="float",
                required=True,
                description="Total shareholder equity.",
            ),
            "ebit": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="EBIT. Defaults to operating_income if 0.",
            ),
            "interest_expense": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Interest expense.",
            ),
            "income_before_tax": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Income before tax.",
            ),
            "income_tax_expense": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Income tax expense.",
            ),
            "operating_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net cash from operations.",
            ),
            "free_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Free cash flow.",
            ),
            "total_debt": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Total debt. Used for ROIC.",
            ),
            "dividends": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Dividends paid. Used for ROIC.",
            ),
        },
        outputs=[
            HelperOutput(
                name="profitability_ratios",
                type="dict",
                description=(
                    "Dict with gross_margin, operating_margin, net_margin, roa, roe, "
                    "roic, ebit_to_revenue, effective_tax_rate, income_quality_ratio, "
                    "fcf_to_ocf_ratio."
                ),
            ),
        ],
        produces_artifacts=["ft_profitability_ratios_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
