"""cash_conversion_cycle — DSO + DIO - DPO = CCC.

Registered name: "cash_conversion_cycle"
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
    accounts_receivable: float,
    revenue: float,
    inventory: float,
    cogs: float,
    accounts_payable: float,
    days_in_period: int = 365,
    accounts_receivable_prior: float | None = None,
    inventory_prior: float | None = None,
    accounts_payable_prior: float | None = None,
) -> dict[str, Any]:
    """Compute Cash Conversion Cycle.

    DSO = (AR / Revenue) * days
    DIO = (Inventory / COGS) * days
    DPO = (AP / COGS) * days
    CCC = DSO + DIO - DPO

    If prior-period balances are provided, uses average balances.

    Args:
        accounts_receivable: AR balance, end of period.
        revenue: Revenue for the period.
        inventory: Inventory balance, end of period.
        cogs: Cost of goods sold for the period.
        accounts_payable: AP balance, end of period.
        days_in_period: Days in the period (default 365 for annual).
        accounts_receivable_prior: Optional prior AR for averaging.
        inventory_prior: Optional prior inventory for averaging.
        accounts_payable_prior: Optional prior AP for averaging.

    Returns:
        Dict with DSO, DIO, DPO, CCC, and YoY delta if priors provided.
    """
    if revenue <= 0:
        raise ValueError("revenue must be positive")
    if cogs <= 0:
        raise ValueError("cogs must be positive")

    # Use average balances if prior provided
    avg_ar = (
        (accounts_receivable + accounts_receivable_prior) / 2.0
        if accounts_receivable_prior is not None
        else accounts_receivable
    )
    avg_inv = (inventory + inventory_prior) / 2.0 if inventory_prior is not None else inventory
    avg_ap = (
        (accounts_payable + accounts_payable_prior) / 2.0
        if accounts_payable_prior is not None
        else accounts_payable
    )

    dso = avg_ar / revenue * days_in_period
    dio = avg_inv / cogs * days_in_period
    dpo = avg_ap / cogs * days_in_period
    ccc = dso + dio - dpo

    return {
        "dso": round(dso, 1),
        "dio": round(dio, 1),
        "dpo": round(dpo, 1),
        "ccc": round(ccc, 1),
        "days_in_period": days_in_period,
        "using_average_balances": any(
            p is not None
            for p in [accounts_receivable_prior, inventory_prior, accounts_payable_prior]
        ),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="cash_conversion_cycle",
        category=Category.BUSINESS_QUALITY,
        one_liner="DSO + DIO - DPO = Cash Conversion Cycle in days.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the Cash Conversion Cycle from AR, inventory, AP, revenue, and COGS. "
            "Lower CCC = faster cash conversion; negative CCC = float-positive business."
        ),
        when_to_use=[
            "Working capital efficiency analysis.",
            "Comparing CCC to peers or tracking trend over time.",
        ],
        when_not_to_use=[
            "Full working capital metrics set — use ft_working_capital_metrics.",
            "Asset turnover analysis — use ft_efficiency_ratios.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "accounts_receivable": HelperParam(
                type="float", required=True, description="AR balance, end of period."
            ),
            "revenue": HelperParam(
                type="float", required=True, description="Revenue for the period."
            ),
            "inventory": HelperParam(
                type="float", required=True, description="Inventory balance, end of period."
            ),
            "cogs": HelperParam(
                type="float", required=True, description="Cost of goods sold for the period."
            ),
            "accounts_payable": HelperParam(
                type="float", required=True, description="AP balance, end of period."
            ),
            "days_in_period": HelperParam(
                type="int",
                required=False,
                default=365,
                description="Days in the period (default 365 for annual, 91 for quarterly).",
            ),
            "accounts_receivable_prior": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Prior AR balance for averaging.",
            ),
            "inventory_prior": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Prior inventory balance for averaging.",
            ),
            "accounts_payable_prior": HelperParam(
                type="float | None",
                required=False,
                default=None,
                description="Prior AP balance for averaging.",
            ),
        },
        outputs=[
            HelperOutput(
                name="cash_conversion_cycle",
                type="dict",
                description="dso, dio, dpo, ccc (all in days), days_in_period.",
            ),
        ],
        produces_artifacts=["cash_conversion_cycle_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
