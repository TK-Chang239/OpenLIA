"""v2.2 wrapper for the ratio_calculator helper.

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.ratio_calculator import (
    execute as _impl,
)
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

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ratio_calculator",
        category=Category.BUSINESS_QUALITY,
        one_liner="Financial ratios across 5 categories with industry-benchmark interpretation.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Calculate profitability, liquidity, leverage, efficiency, and valuation ratios "
            "from financial statement data, with benchmark-based interpretation for each."
        ),
        when_to_use=[
            "Generating a standard ratio panel from income statement, balance sheet, "
            "and market data inputs.",
            "When benchmark-flagged ratio interpretation is needed alongside raw values.",
            "Computing a single ratio category (e.g. profitability only) via the category param.",
        ],
        when_not_to_use=[
            "Full DCF valuation — use dcf_valuation instead.",
            "SaaS-specific KPIs (MRR, NRR, LTV:CAC) — use saas_metrics instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "income_statement": HelperParam(
                type="dict",
                description=(
                    "Income statement data: revenue, cost_of_goods_sold, "
                    "operating_income, net_income, ebitda, interest_expense."
                ),
                required=True,
            ),
            "balance_sheet": HelperParam(
                type="dict",
                default=None,
                description=(
                    "Balance sheet data: current_assets, current_liabilities, inventory, "
                    "total_equity, total_assets, total_debt, cash_and_equivalents, "
                    "accounts_receivable."
                ),
                required=False,
            ),
            "cash_flow": HelperParam(
                type="dict",
                default=None,
                description="Cash flow data: operating_cash_flow, total_debt_service.",
                required=False,
            ),
            "market_data": HelperParam(
                type="dict",
                default=None,
                description=(
                    "Market data: market_cap, share_price, shares_outstanding, "
                    "earnings_growth_rate."
                ),
                required=False,
            ),
            "category": HelperParam(
                type="str",
                default=None,
                description=(
                    "Compute only one category: "
                    "profitability, liquidity, leverage, efficiency, or valuation."
                ),
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="ratio_panel",
                type="ratio_panel",
                description=(
                    "Dict keyed by category, each containing ratio name, value, "
                    "formula, and benchmark interpretation."
                ),
            ),
        ],
        produces_artifacts=["ratio_panel"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
