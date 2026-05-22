"""ft_altman_z_score — original 5-factor Altman Z-Score via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.models.altman_model as _alt

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

# Z-Score interpretation thresholds (original Altman 1968 model)
_DISTRESS_THRESHOLD = 1.81
_GREY_ZONE_THRESHOLD = 2.99


def execute(
    current_assets: float,
    current_liabilities: float,
    total_assets: float,
    retained_earnings: float,
    ebit: float,
    market_cap: float,
    total_liabilities: float,
    total_revenue: float,
) -> dict[str, Any]:
    """Compute the Altman Z-Score (original 5-factor 1968 model).

    Formula:
        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
    where:
        X1 = Working Capital / Total Assets
        X2 = Retained Earnings / Total Assets
        X3 = EBIT / Total Assets
        X4 = Market Cap / Total Liabilities
        X5 = Revenue / Total Assets
    """
    if total_assets == 0:
        raise ValueError("total_assets must be non-zero")

    working_capital = current_assets - current_liabilities

    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = market_cap / total_liabilities if total_liabilities != 0 else 0.0
    x5 = total_revenue / total_assets

    z_score = float(
        _alt.get_altman_z_score(
            working_capital_to_total_assets_ratio=x1,
            retained_earnings_to_total_assets_ratio=x2,
            earnings_before_interest_and_taxes_to_total_assets_ratio=x3,
            market_value_of_equity_to_book_value_of_total_liabilities_ratio=x4,
            sales_to_total_assets_ratio=x5,
        )
    )

    if z_score > _GREY_ZONE_THRESHOLD:
        zone = "safe"
    elif z_score > _DISTRESS_THRESHOLD:
        zone = "grey"
    else:
        zone = "distress"

    return {
        "z_score": round(z_score, 4),
        "zone": zone,
        "components": {
            "x1_working_capital_to_assets": round(x1, 4),
            "x2_retained_earnings_to_assets": round(x2, 4),
            "x3_ebit_to_assets": round(x3, 4),
            "x4_market_cap_to_liabilities": round(x4, 4),
            "x5_revenue_to_assets": round(x5, 4),
        },
        "thresholds": {
            "safe_above": _GREY_ZONE_THRESHOLD,
            "distress_below": _DISTRESS_THRESHOLD,
        },
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_altman_z_score",
        category=Category.BUSINESS_QUALITY,
        one_liner="Altman Z-Score: 5-factor bankruptcy probability model.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the original Altman (1968) Z-Score to assess financial distress risk "
            "using FinanceToolkit's Altman model function."
        ),
        when_to_use=[
            "Assessing financial health and bankruptcy risk in an equity research report.",
            "Screening for financially distressed companies.",
        ],
        when_not_to_use=[
            "Non-manufacturing companies where the original Z-Score has reduced accuracy "
            "(use Piotroski F-Score as supplementary — ft_piotroski_f_score).",
            "Piotroski quality scoring — use ft_piotroski_f_score.",
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
            "total_assets": HelperParam(
                type="float",
                required=True,
                description="Total assets.",
            ),
            "retained_earnings": HelperParam(
                type="float",
                required=True,
                description="Retained earnings.",
            ),
            "ebit": HelperParam(
                type="float",
                required=True,
                description="Earnings before interest and taxes.",
            ),
            "market_cap": HelperParam(
                type="float",
                required=True,
                description="Market capitalization.",
            ),
            "total_liabilities": HelperParam(
                type="float",
                required=True,
                description="Total liabilities.",
            ),
            "total_revenue": HelperParam(
                type="float",
                required=True,
                description="Total revenue.",
            ),
        },
        outputs=[
            HelperOutput(
                name="altman_z_score",
                type="dict",
                description=(
                    "Dict with z_score (float), zone ('safe'/'grey'/'distress'), "
                    "components (X1-X5 ratios), and thresholds."
                ),
            ),
        ],
        produces_artifacts=["ft_altman_z_score_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
