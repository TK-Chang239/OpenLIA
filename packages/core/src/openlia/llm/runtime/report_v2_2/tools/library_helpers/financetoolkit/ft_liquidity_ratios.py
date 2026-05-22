"""ft_liquidity_ratios — current, quick, and cash ratios via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.liquidity_model as _liq

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
    current_assets: float,
    current_liabilities: float,
    cash_and_equivalents: float = 0.0,
    accounts_receivable: float = 0.0,
    marketable_securities: float = 0.0,
    inventory: float = 0.0,
    operating_cash_flow: float = 0.0,
    accounts_payable: float = 0.0,
) -> dict[str, Any]:
    """Compute liquidity ratios from balance sheet and cash flow inputs."""
    current_ratio = float(_liq.get_current_ratio(current_assets, current_liabilities))
    quick_ratio = float(
        _liq.get_quick_ratio(
            cash_and_equivalents,
            accounts_receivable,
            marketable_securities,
            current_liabilities,
        )
    )
    cash_ratio = float(
        _liq.get_cash_ratio(cash_and_equivalents, marketable_securities, current_liabilities)
    )
    working_capital = float(_liq.get_working_capital(current_assets, current_liabilities))

    ocf_ratio: float | None = None
    if current_liabilities != 0 and operating_cash_flow != 0:
        ocf_ratio = float(
            _liq.get_operating_cash_flow_ratio(operating_cash_flow, current_liabilities)
        )

    short_term_coverage: float | None = None
    if operating_cash_flow != 0 and accounts_payable != 0:
        short_term_coverage = float(
            _liq.get_short_term_coverage_ratio(
                operating_cash_flow,
                accounts_receivable,
                inventory,
                accounts_payable,
            )
        )

    return {
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        "cash_ratio": cash_ratio,
        "working_capital": working_capital,
        "operating_cash_flow_ratio": ocf_ratio,
        "short_term_coverage_ratio": short_term_coverage,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_liquidity_ratios",
        category=Category.BUSINESS_QUALITY,
        one_liner="Current, quick, and cash ratios from balance sheet line items.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute liquidity ratios (current, quick, cash, OCF) using FinanceToolkit "
            "model functions applied to user-supplied balance sheet and cash flow scalars."
        ),
        when_to_use=[
            "Assessing short-term solvency from EODHD balance sheet output.",
            "Generating a liquidity section in an equity research report.",
        ],
        when_not_to_use=[
            "Full ratio panel across all categories — use ft_profitability_ratios or the "
            "legacy ratio_calculator instead.",
            "Solvency/leverage ratios — use ft_solvency_ratios.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "current_assets": HelperParam(
                type="float",
                required=True,
                description="Total current assets.",
            ),
            "current_liabilities": HelperParam(
                type="float",
                required=True,
                description="Total current liabilities.",
            ),
            "cash_and_equivalents": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Cash and cash equivalents.",
            ),
            "accounts_receivable": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net accounts receivable.",
            ),
            "marketable_securities": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Short-term marketable securities.",
            ),
            "inventory": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Inventory balance.",
            ),
            "operating_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net cash from operations.",
            ),
            "accounts_payable": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Accounts payable balance.",
            ),
        },
        outputs=[
            HelperOutput(
                name="liquidity_ratios",
                type="dict",
                description=(
                    "Dict with current_ratio, quick_ratio, cash_ratio, working_capital, "
                    "operating_cash_flow_ratio, short_term_coverage_ratio."
                ),
            ),
        ],
        produces_artifacts=["ft_liquidity_ratios_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
