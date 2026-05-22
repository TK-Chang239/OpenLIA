"""ft_working_capital_metrics — NWC, NWC/revenue, and cash conversion cycle."""

from __future__ import annotations

from typing import Any

import financetoolkit.ratios.efficiency_model as _eff
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
    revenue: float,
    cost_of_goods_sold: float = 0.0,
    inventory: float = 0.0,
    accounts_receivable: float = 0.0,
    accounts_payable: float = 0.0,
    cash_and_equivalents: float = 0.0,
    operating_cash_flow: float = 0.0,
) -> dict[str, Any]:
    """Compute working capital and cash conversion metrics."""
    nwc = float(_liq.get_working_capital(current_assets, current_liabilities))

    nwc_to_revenue: float | None = None
    if revenue != 0:
        nwc_to_revenue = nwc / revenue

    current_ratio = float(_liq.get_current_ratio(current_assets, current_liabilities))

    # Non-cash working capital (excludes cash from current assets)
    non_cash_nwc: float | None = None
    if cash_and_equivalents != 0:
        non_cash_nwc = nwc - cash_and_equivalents

    # Days metrics and CCC
    days_inventory: float | None = None
    days_sales: float | None = None
    days_payable: float | None = None
    cash_conversion_cycle: float | None = None
    operating_cycle: float | None = None

    if inventory != 0 and cost_of_goods_sold != 0:
        days_inventory = float(
            _eff.get_days_of_inventory_outstanding(inventory, cost_of_goods_sold)
        )

    if accounts_receivable != 0 and revenue != 0:
        days_sales = float(_eff.get_days_of_sales_outstanding(accounts_receivable, revenue))

    if accounts_payable != 0 and cost_of_goods_sold != 0:
        days_payable = float(
            _eff.get_days_of_accounts_payable_outstanding(accounts_payable, cost_of_goods_sold)
        )

    if days_inventory is not None and days_sales is not None:
        operating_cycle = float(_eff.get_operating_cycle(days_inventory, days_sales))

    if days_inventory is not None and days_sales is not None and days_payable is not None:
        cash_conversion_cycle = float(
            _eff.get_cash_conversion_cycle(days_inventory, days_sales, days_payable)
        )

    ocf_to_nwc: float | None = None
    if nwc != 0 and operating_cash_flow != 0:
        ocf_to_nwc = operating_cash_flow / nwc

    return {
        "net_working_capital": nwc,
        "nwc_to_revenue": nwc_to_revenue,
        "non_cash_nwc": non_cash_nwc,
        "current_ratio": current_ratio,
        "days_inventory_outstanding": days_inventory,
        "days_sales_outstanding": days_sales,
        "days_payable_outstanding": days_payable,
        "operating_cycle": operating_cycle,
        "cash_conversion_cycle": cash_conversion_cycle,
        "ocf_to_nwc": ocf_to_nwc,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_working_capital_metrics",
        category=Category.BUSINESS_QUALITY,
        one_liner="NWC, NWC/revenue, cash conversion cycle, and days outstanding.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute working capital efficiency metrics — NWC, NWC/revenue, CCC, and "
            "days outstanding — using FinanceToolkit model functions."
        ),
        when_to_use=[
            "Analyzing operational cash efficiency and working capital management.",
            "Computing CCC for manufacturing, retail, or distribution companies.",
        ],
        when_not_to_use=[
            "Pure liquidity ratios (current/quick/cash) — use ft_liquidity_ratios.",
            "Efficiency ratios without NWC focus — use ft_efficiency_ratios.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "current_assets": HelperParam(
                type="float", required=True, description="Total current assets."
            ),
            "current_liabilities": HelperParam(
                type="float", required=True, description="Total current liabilities."
            ),
            "revenue": HelperParam(type="float", required=True, description="Total revenue."),
            "cost_of_goods_sold": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="COGS. Required for days inventory and days payable.",
            ),
            "inventory": HelperParam(
                type="float", required=False, default=0.0, description="Inventory balance."
            ),
            "accounts_receivable": HelperParam(
                type="float", required=False, default=0.0, description="Net accounts receivable."
            ),
            "accounts_payable": HelperParam(
                type="float", required=False, default=0.0, description="Accounts payable."
            ),
            "cash_and_equivalents": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Cash. Used to compute non-cash NWC.",
            ),
            "operating_cash_flow": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Operating CF for OCF/NWC ratio.",
            ),
        },
        outputs=[
            HelperOutput(
                name="working_capital_metrics",
                type="dict",
                description=(
                    "Dict with net_working_capital, nwc_to_revenue, non_cash_nwc, "
                    "current_ratio, days_inventory_outstanding, days_sales_outstanding, "
                    "days_payable_outstanding, operating_cycle, cash_conversion_cycle, "
                    "ocf_to_nwc."
                ),
            ),
        ],
        produces_artifacts=["ft_working_capital_metrics_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
