"""total_shareholder_yield — Dividend + buyback + debt paydown yield.

Registered name: "total_shareholder_yield"
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
    market_cap: float,
    dividends_paid: float,
    buybacks: float,
    net_debt_repayment: float = 0.0,
) -> dict[str, Any]:
    """Compute total shareholder yield.

    TSY = dividend_yield + buyback_yield + debt_paydown_yield

    Args:
        market_cap: Current market capitalization.
        dividends_paid: Total dividends paid in period (positive = outflow).
        buybacks: Share repurchases in period (positive = outflow).
        net_debt_repayment: Net debt repaid in period (positive = debt reduced).

    Returns:
        Dict with individual yields and combined TSY.
    """
    if market_cap <= 0:
        raise ValueError("market_cap must be positive")

    dividend_yield = dividends_paid / market_cap
    buyback_yield = buybacks / market_cap
    debt_paydown_yield = net_debt_repayment / market_cap
    total_shareholder_yield = dividend_yield + buyback_yield + debt_paydown_yield

    return {
        "market_cap": market_cap,
        "dividends_paid": dividends_paid,
        "buybacks": buybacks,
        "net_debt_repayment": net_debt_repayment,
        "dividend_yield": round(dividend_yield, 4),
        "buyback_yield": round(buyback_yield, 4),
        "debt_paydown_yield": round(debt_paydown_yield, 4),
        "total_shareholder_yield": round(total_shareholder_yield, 4),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="total_shareholder_yield",
        category=Category.BUSINESS_QUALITY,
        one_liner="Dividend yield + buyback yield + debt paydown yield = TSY.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute Total Shareholder Yield as the sum of dividend yield, buyback yield, "
            "and debt paydown yield relative to market cap."
        ),
        when_to_use=[
            "Comparing capital return attractiveness across companies.",
            "When buybacks are material and dividend-only yield understates total return.",
        ],
        when_not_to_use=[
            "Capital allocation composition over time — use capital_allocation_history.",
            "Forward dividend sustainability — use ft_dividend_metrics.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "market_cap": HelperParam(
                type="float",
                required=True,
                description="Current market capitalization.",
            ),
            "dividends_paid": HelperParam(
                type="float",
                required=True,
                description="Dividends paid in the period.",
            ),
            "buybacks": HelperParam(
                type="float",
                required=True,
                description="Share repurchases in the period.",
            ),
            "net_debt_repayment": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Net debt repaid in the period.",
            ),
        },
        outputs=[
            HelperOutput(
                name="total_shareholder_yield",
                type="dict",
                description=(
                    "dividend_yield, buyback_yield, debt_paydown_yield, total_shareholder_yield."
                ),
            ),
        ],
        produces_artifacts=["total_shareholder_yield_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
