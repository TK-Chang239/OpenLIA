"""ft_growth_metrics — YoY revenue, earnings, and FCF growth rates."""

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


def _yoy_growth(current: float, prior: float) -> float | None:
    """YoY growth rate. Returns None if prior is zero."""
    if prior == 0:
        return None
    return (current - prior) / abs(prior)


def execute(
    revenue: float,
    revenue_prior: float,
    net_income: float,
    net_income_prior: float,
    gross_profit: float = 0.0,
    gross_profit_prior: float = 0.0,
    operating_income: float = 0.0,
    operating_income_prior: float = 0.0,
    free_cash_flow: float = 0.0,
    free_cash_flow_prior: float = 0.0,
    operating_cash_flow: float = 0.0,
    operating_cash_flow_prior: float = 0.0,
    eps: float = 0.0,
    eps_prior: float = 0.0,
    total_assets: float = 0.0,
    total_assets_prior: float = 0.0,
) -> dict[str, Any]:
    """Compute YoY growth rates for key financial metrics.

    FinanceToolkit's growth_model only exposes present_value_of_growth_opportunities,
    so growth is computed directly here using the standard formula:
        growth = (current - prior) / |prior|
    """
    return {
        "revenue_growth": _yoy_growth(revenue, revenue_prior),
        "gross_profit_growth": (
            _yoy_growth(gross_profit, gross_profit_prior) if gross_profit_prior != 0 else None
        ),
        "operating_income_growth": (
            _yoy_growth(operating_income, operating_income_prior)
            if operating_income_prior != 0
            else None
        ),
        "net_income_growth": _yoy_growth(net_income, net_income_prior),
        "eps_growth": (_yoy_growth(eps, eps_prior) if eps_prior != 0 else None),
        "free_cash_flow_growth": (
            _yoy_growth(free_cash_flow, free_cash_flow_prior) if free_cash_flow_prior != 0 else None
        ),
        "operating_cash_flow_growth": (
            _yoy_growth(operating_cash_flow, operating_cash_flow_prior)
            if operating_cash_flow_prior != 0
            else None
        ),
        "total_assets_growth": (
            _yoy_growth(total_assets, total_assets_prior) if total_assets_prior != 0 else None
        ),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_growth_metrics",
        category=Category.BUSINESS_QUALITY,
        one_liner="YoY revenue, earnings, and FCF growth rates from two periods of data.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute year-over-year growth rates for revenue, net income, gross profit, "
            "operating income, EPS, FCF, and OCF from current and prior-period scalars."
        ),
        when_to_use=[
            "Generating a growth section in an equity research report.",
            "Comparing current-quarter results against the prior-year period.",
        ],
        when_not_to_use=[
            "Per-share metrics (EPS, BVPS) standalone — use ft_per_share_metrics.",
            "Multi-year CAGR calculations — compute manually from time-series data.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "revenue": HelperParam(
                type="float", required=True, description="Current period revenue."
            ),
            "revenue_prior": HelperParam(
                type="float", required=True, description="Prior period revenue."
            ),
            "net_income": HelperParam(
                type="float", required=True, description="Current period net income."
            ),
            "net_income_prior": HelperParam(
                type="float", required=True, description="Prior period net income."
            ),
            "gross_profit": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Current period gross profit.",
            ),
            "gross_profit_prior": HelperParam(
                type="float", required=False, default=0.0, description="Prior period gross profit."
            ),
            "operating_income": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Current period operating income.",
            ),
            "operating_income_prior": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Prior period operating income.",
            ),
            "free_cash_flow": HelperParam(
                type="float", required=False, default=0.0, description="Current period FCF."
            ),
            "free_cash_flow_prior": HelperParam(
                type="float", required=False, default=0.0, description="Prior period FCF."
            ),
            "operating_cash_flow": HelperParam(
                type="float", required=False, default=0.0, description="Current period OCF."
            ),
            "operating_cash_flow_prior": HelperParam(
                type="float", required=False, default=0.0, description="Prior period OCF."
            ),
            "eps": HelperParam(
                type="float", required=False, default=0.0, description="Current period EPS."
            ),
            "eps_prior": HelperParam(
                type="float", required=False, default=0.0, description="Prior period EPS."
            ),
            "total_assets": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Current period total assets.",
            ),
            "total_assets_prior": HelperParam(
                type="float", required=False, default=0.0, description="Prior period total assets."
            ),
        },
        outputs=[
            HelperOutput(
                name="growth_metrics",
                type="dict",
                description=(
                    "Dict with YoY growth rates (as decimals): revenue_growth, "
                    "gross_profit_growth, operating_income_growth, net_income_growth, "
                    "eps_growth, free_cash_flow_growth, operating_cash_flow_growth, "
                    "total_assets_growth. Null when prior period is zero."
                ),
            ),
        ],
        produces_artifacts=["ft_growth_metrics_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
