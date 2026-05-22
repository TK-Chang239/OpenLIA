"""ft_efficiency_ratios — asset/inventory/receivables turnover and days outstanding metrics."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.efficiency_model as _eff

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
    total_assets: float,
    cost_of_goods_sold: float = 0.0,
    inventory: float = 0.0,
    accounts_receivable: float = 0.0,
    accounts_payable: float = 0.0,
    gross_profit: float = 0.0,
    operating_expenses: float = 0.0,
    sga_expense: float = 0.0,
    fixed_assets: float = 0.0,
    operating_cash_flow: float = 0.0,
) -> dict[str, Any]:
    """Compute efficiency ratios from income statement and balance sheet inputs."""
    asset_turnover = float(_eff.get_asset_turnover_ratio(revenue, total_assets))

    inventory_turnover: float | None = None
    if inventory != 0 and cost_of_goods_sold != 0:
        inventory_turnover = float(_eff.get_inventory_turnover_ratio(cost_of_goods_sold, inventory))

    receivables_turnover: float | None = None
    days_sales_outstanding: float | None = None
    if accounts_receivable != 0:
        receivables_turnover = float(_eff.get_receivables_turnover(accounts_receivable, revenue))
        days_sales_outstanding = float(
            _eff.get_days_of_sales_outstanding(accounts_receivable, revenue)
        )

    days_inventory_outstanding: float | None = None
    if inventory != 0 and cost_of_goods_sold != 0:
        days_inventory_outstanding = float(
            _eff.get_days_of_inventory_outstanding(inventory, cost_of_goods_sold)
        )

    days_payable_outstanding: float | None = None
    if accounts_payable != 0 and cost_of_goods_sold != 0:
        days_payable_outstanding = float(
            _eff.get_days_of_accounts_payable_outstanding(accounts_payable, cost_of_goods_sold)
        )

    cash_conversion_cycle: float | None = None
    if (
        days_sales_outstanding is not None
        and days_inventory_outstanding is not None
        and days_payable_outstanding is not None
    ):
        cash_conversion_cycle = float(
            _eff.get_cash_conversion_cycle(
                days_inventory_outstanding,
                days_sales_outstanding,
                days_payable_outstanding,
            )
        )

    operating_cycle: float | None = None
    if days_sales_outstanding is not None and days_inventory_outstanding is not None:
        operating_cycle = float(
            _eff.get_operating_cycle(days_inventory_outstanding, days_sales_outstanding)
        )

    fixed_asset_turnover: float | None = None
    if fixed_assets != 0:
        fixed_asset_turnover = float(_eff.get_fixed_asset_turnover(revenue, fixed_assets))

    cash_conversion_efficiency: float | None = None
    if operating_cash_flow != 0 and revenue != 0:
        cash_conversion_efficiency = float(
            _eff.get_cash_conversion_efficiency(operating_cash_flow, revenue)
        )

    operating_ratio: float | None = None
    if operating_expenses != 0:
        operating_ratio = float(_eff.get_operating_ratio(operating_expenses, revenue))

    sga_to_revenue: float | None = None
    if sga_expense != 0:
        sga_to_revenue = float(_eff.get_sga_to_revenue_ratio(sga_expense, revenue))

    return {
        "asset_turnover": asset_turnover,
        "inventory_turnover": inventory_turnover,
        "receivables_turnover": receivables_turnover,
        "days_sales_outstanding": days_sales_outstanding,
        "days_inventory_outstanding": days_inventory_outstanding,
        "days_payable_outstanding": days_payable_outstanding,
        "cash_conversion_cycle": cash_conversion_cycle,
        "operating_cycle": operating_cycle,
        "fixed_asset_turnover": fixed_asset_turnover,
        "cash_conversion_efficiency": cash_conversion_efficiency,
        "operating_ratio": operating_ratio,
        "sga_to_revenue": sga_to_revenue,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_efficiency_ratios",
        category=Category.BUSINESS_QUALITY,
        one_liner="Asset/inventory/receivables turnover and days-outstanding metrics.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute operational efficiency ratios using FinanceToolkit model functions "
            "applied to user-supplied income statement and balance sheet scalars."
        ),
        when_to_use=[
            "Measuring how efficiently a company uses its assets to generate revenue.",
            "Computing cash conversion cycle for working capital analysis.",
        ],
        when_not_to_use=[
            "Liquidity ratios — use ft_liquidity_ratios.",
            "Working capital metrics with NWC focus — use ft_working_capital_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "revenue": HelperParam(
                type="float",
                required=True,
                description="Total revenue.",
            ),
            "total_assets": HelperParam(
                type="float",
                required=True,
                description="Total assets.",
            ),
            "cost_of_goods_sold": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Cost of goods sold. Required for inventory turnover.",
            ),
            "inventory": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Inventory balance.",
            ),
            "accounts_receivable": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net accounts receivable.",
            ),
            "accounts_payable": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Accounts payable balance.",
            ),
            "gross_profit": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Gross profit.",
            ),
            "operating_expenses": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Total operating expenses.",
            ),
            "sga_expense": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Selling, general and administrative expenses.",
            ),
            "fixed_assets": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net PP&E / fixed assets.",
            ),
            "operating_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net cash from operations.",
            ),
        },
        outputs=[
            HelperOutput(
                name="efficiency_ratios",
                type="dict",
                description=(
                    "Dict with asset_turnover, inventory_turnover, receivables_turnover, "
                    "days_sales_outstanding, days_inventory_outstanding, "
                    "days_payable_outstanding, cash_conversion_cycle, operating_cycle, "
                    "fixed_asset_turnover, cash_conversion_efficiency, operating_ratio, "
                    "sga_to_revenue."
                ),
            ),
        ],
        produces_artifacts=["ft_efficiency_ratios_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
