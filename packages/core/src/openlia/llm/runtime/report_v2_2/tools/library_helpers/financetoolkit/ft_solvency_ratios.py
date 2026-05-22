"""ft_solvency_ratios — debt-to-equity, debt-to-assets, interest coverage via FinanceToolkit."""

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
    operating_income: float,
    interest_expense: float,
    depreciation_and_amortization: float = 0.0,
    net_debt: float = 0.0,
    cash_flow_from_operations: float = 0.0,
    capital_expenditure: float = 0.0,
    free_cash_flow: float = 0.0,
    market_cap: float = 0.0,
    dividends: float = 0.0,
) -> dict[str, Any]:
    """Compute solvency ratios from balance sheet and income statement inputs."""
    debt_to_equity = float(_solv.get_debt_to_equity_ratio(total_debt, total_equity))
    debt_to_assets = float(_solv.get_debt_to_assets_ratio(total_debt, total_assets))
    interest_coverage = float(
        _solv.get_interest_coverage_ratio(
            operating_income, depreciation_and_amortization, interest_expense
        )
    )
    equity_multiplier = float(_solv.get_equity_multiplier(total_assets, total_equity))

    net_debt_to_ebitda: float | None = None
    if (operating_income + depreciation_and_amortization) != 0 and net_debt != 0:
        net_debt_to_ebitda = float(
            _solv.get_net_debt_to_ebitda_ratio(
                operating_income, depreciation_and_amortization, net_debt
            )
        )

    capex_coverage: float | None = None
    if capital_expenditure != 0 and cash_flow_from_operations != 0:
        capex_coverage = float(
            _solv.get_capex_coverage_ratio(cash_flow_from_operations, capital_expenditure)
        )

    fcf_yield: float | None = None
    if free_cash_flow != 0 and market_cap != 0:
        fcf_yield = float(_solv.get_free_cash_flow_yield(free_cash_flow, market_cap))

    return {
        "debt_to_equity": debt_to_equity,
        "debt_to_assets": debt_to_assets,
        "interest_coverage": interest_coverage,
        "equity_multiplier": equity_multiplier,
        "net_debt_to_ebitda": net_debt_to_ebitda,
        "capex_coverage_ratio": capex_coverage,
        "free_cash_flow_yield": fcf_yield,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_solvency_ratios",
        category=Category.BUSINESS_QUALITY,
        one_liner="Debt-to-equity, interest coverage, and leverage ratios.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute solvency and leverage ratios using FinanceToolkit model functions "
            "applied to user-supplied balance sheet and income statement scalars."
        ),
        when_to_use=[
            "Assessing long-term financial stability and debt burden.",
            "Generating a leverage/solvency section in an equity research report.",
        ],
        when_not_to_use=[
            "Short-term liquidity — use ft_liquidity_ratios.",
            "Full profitability analysis — use ft_profitability_ratios.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "total_debt": HelperParam(
                type="float",
                required=True,
                description="Total debt (short-term + long-term).",
            ),
            "total_equity": HelperParam(
                type="float",
                required=True,
                description="Total shareholder equity.",
            ),
            "total_assets": HelperParam(
                type="float",
                required=True,
                description="Total assets.",
            ),
            "operating_income": HelperParam(
                type="float",
                required=True,
                description="Operating income (EBIT).",
            ),
            "interest_expense": HelperParam(
                type="float",
                required=True,
                description="Interest expense.",
            ),
            "depreciation_and_amortization": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="D&A (used for interest coverage and EV/EBITDA).",
            ),
            "net_debt": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net debt = total debt - cash. Supply for net_debt_to_ebitda.",
            ),
            "cash_flow_from_operations": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Operating cash flow. Supply for capex_coverage_ratio.",
            ),
            "capital_expenditure": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Capital expenditure (absolute value). Supply for capex_coverage.",
            ),
            "free_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Free cash flow. Supply for fcf_yield.",
            ),
            "market_cap": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Market capitalization. Supply for fcf_yield.",
            ),
        },
        outputs=[
            HelperOutput(
                name="solvency_ratios",
                type="dict",
                description=(
                    "Dict with debt_to_equity, debt_to_assets, interest_coverage, "
                    "equity_multiplier, net_debt_to_ebitda, capex_coverage_ratio, "
                    "free_cash_flow_yield."
                ),
            ),
        ],
        produces_artifacts=["ft_solvency_ratios_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
