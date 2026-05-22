"""organic_vs_inorganic_growth — Revenue growth decomposition: organic/FX/acquisition.

Registered name: "organic_vs_inorganic_growth"
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
    revenue_prior: float,
    revenue_current: float,
    fx_impact: float = 0.0,
    acquisition_revenue: float = 0.0,
) -> dict[str, Any]:
    """Decompose revenue growth into organic, FX, and acquisition components.

    Total growth = organic + FX + acquisition
    organic = total - FX - acquisition (all expressed as % of prior revenue)

    Args:
        revenue_prior: Prior period revenue.
        revenue_current: Current period revenue.
        fx_impact: FX headwind/tailwind (positive = tailwind, adds to reported).
        acquisition_revenue: Revenue contribution from acquisitions in current period.

    Returns:
        Dict with total growth, organic growth, FX impact, and acquisition contribution.
    """
    if revenue_prior <= 0:
        raise ValueError("revenue_prior must be positive")

    total_growth = revenue_current - revenue_prior
    total_growth_pct = total_growth / revenue_prior * 100.0

    fx_pct = fx_impact / revenue_prior * 100.0
    acquisition_pct = acquisition_revenue / revenue_prior * 100.0
    organic_pct = total_growth_pct - fx_pct - acquisition_pct
    organic_absolute = organic_pct / 100.0 * revenue_prior

    return {
        "revenue_prior": revenue_prior,
        "revenue_current": revenue_current,
        "total_growth": round(total_growth, 2),
        "total_growth_pct": round(total_growth_pct, 2),
        "fx_impact": round(fx_impact, 2),
        "fx_impact_pct": round(fx_pct, 2),
        "acquisition_revenue": round(acquisition_revenue, 2),
        "acquisition_pct": round(acquisition_pct, 2),
        "organic_growth": round(organic_absolute, 2),
        "organic_growth_pct": round(organic_pct, 2),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="organic_vs_inorganic_growth",
        category=Category.BUSINESS_QUALITY,
        one_liner="Revenue growth split into organic, FX, and acquisition components.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Decompose reported revenue growth into organic, FX, and acquisition-driven "
            "components. Organic growth is the residual after removing FX and M&A."
        ),
        when_to_use=[
            "When a company has made acquisitions and you need to isolate organic performance.",
            "When FX is material and management reports constant-currency growth.",
        ],
        when_not_to_use=[
            "Constant-currency growth without M&A decomp — use currency_neutral_growth.",
            "Full margin trajectory — use margin_trajectory_regression.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "revenue_prior": HelperParam(
                type="float", required=True, description="Prior period revenue."
            ),
            "revenue_current": HelperParam(
                type="float", required=True, description="Current period revenue."
            ),
            "fx_impact": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="FX impact on reported revenue (positive = tailwind).",
            ),
            "acquisition_revenue": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Revenue from acquisitions in current period.",
            ),
        },
        outputs=[
            HelperOutput(
                name="organic_vs_inorganic_growth",
                type="dict",
                description=(
                    "total_growth_pct, organic_growth_pct, fx_impact_pct, acquisition_pct."
                ),
            ),
        ],
        produces_artifacts=["organic_vs_inorganic_growth_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
