"""ft_piotroski_f_score — Piotroski F-Score financial health indicator via FinanceToolkit."""

from __future__ import annotations

from typing import Any

import financetoolkit.models.piotroski_model as _pio

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
    net_income: float,
    total_assets: float,
    operating_cash_flow: float,
    total_debt_current: float,
    total_debt_prior: float,
    current_assets: float,
    current_liabilities: float,
    current_assets_prior: float,
    current_liabilities_prior: float,
    shares_outstanding: float,
    shares_outstanding_prior: float,
    gross_profit: float,
    revenue: float,
    gross_profit_prior: float,
    revenue_prior: float,
    total_assets_prior: float,
    net_income_prior: float,
) -> dict[str, Any]:
    """Compute the Piotroski F-Score (9-point scale).

    Scores each of 9 binary criteria (0 or 1) and sums to an F-Score.
    Score 8-9: strong; 5-7: neutral; 0-4: weak.
    """
    if total_assets == 0 or total_assets_prior == 0:
        raise ValueError("total_assets and total_assets_prior must be non-zero")

    # Profitability signals
    roa = net_income / total_assets
    roa_prior = net_income_prior / total_assets_prior

    roa_criteria = int(roa > 0)
    ocf_criteria = int(operating_cash_flow > 0)
    delta_roa_criteria = int(roa > roa_prior)
    accruals_criteria = int(operating_cash_flow / total_assets > roa)

    # Leverage, liquidity, and source of funds signals
    leverage = total_debt_current / total_assets
    leverage_prior = total_debt_prior / total_assets_prior
    change_leverage_criteria = int(leverage < leverage_prior)

    current_ratio = current_assets / current_liabilities if current_liabilities != 0 else 0.0
    current_ratio_prior = (
        current_assets_prior / current_liabilities_prior if current_liabilities_prior != 0 else 0.0
    )
    change_current_ratio_criteria = int(current_ratio > current_ratio_prior)
    no_dilution_criteria = int(shares_outstanding <= shares_outstanding_prior)

    # Operating efficiency signals
    gross_margin = gross_profit / revenue if revenue != 0 else 0.0
    gross_margin_prior = gross_profit_prior / revenue_prior if revenue_prior != 0 else 0.0
    gross_margin_criteria = int(gross_margin > gross_margin_prior)

    asset_turnover = revenue / total_assets
    asset_turnover_prior = revenue_prior / total_assets_prior
    asset_turnover_criteria = int(asset_turnover > asset_turnover_prior)

    f_score = int(
        _pio.get_piotroski_score(
            return_on_assets_criteria=roa_criteria,
            operating_cashflow_criteria=ocf_criteria,
            change_in_return_on_asset_criteria=delta_roa_criteria,
            accruals_criteria=accruals_criteria,
            change_in_leverage_criteria=change_leverage_criteria,
            change_in_current_ratio_criteria=change_current_ratio_criteria,
            number_of_shares_criteria=no_dilution_criteria,
            gross_margin_criteria=gross_margin_criteria,
            asset_turnover_ratio_criteria=asset_turnover_criteria,
        )
    )

    if f_score >= 8:
        strength = "strong"
    elif f_score >= 5:
        strength = "neutral"
    else:
        strength = "weak"

    return {
        "f_score": f_score,
        "strength": strength,
        "criteria": {
            "profitability": {
                "roa_positive": roa_criteria,
                "operating_cf_positive": ocf_criteria,
                "roa_improving": delta_roa_criteria,
                "accruals_low": accruals_criteria,
            },
            "leverage_liquidity": {
                "leverage_decreasing": change_leverage_criteria,
                "current_ratio_improving": change_current_ratio_criteria,
                "no_dilution": no_dilution_criteria,
            },
            "operating_efficiency": {
                "gross_margin_improving": gross_margin_criteria,
                "asset_turnover_improving": asset_turnover_criteria,
            },
        },
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="ft_piotroski_f_score",
        category=Category.BUSINESS_QUALITY,
        one_liner="Piotroski F-Score: 9-point fundamental quality indicator.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the Piotroski F-Score using FinanceToolkit's Piotroski model function "
            "applied to current and prior-period financial statement scalars."
        ),
        when_to_use=[
            "Assessing fundamental financial quality and trend in an equity research report.",
            "Screening for improving vs. deteriorating businesses.",
        ],
        when_not_to_use=[
            "Bankruptcy risk assessment — use ft_altman_z_score.",
            "When prior-period data is not available (F-Score requires two periods).",
        ],
    ),
    contract=MechanicalContract(
        params={
            "net_income": HelperParam(
                type="float", required=True, description="Current period net income."
            ),
            "total_assets": HelperParam(
                type="float", required=True, description="Current period total assets."
            ),
            "operating_cash_flow": HelperParam(
                type="float", required=True, description="Current period operating CF."
            ),
            "total_debt_current": HelperParam(
                type="float", required=True, description="Current period total debt."
            ),
            "total_debt_prior": HelperParam(
                type="float", required=True, description="Prior period total debt."
            ),
            "current_assets": HelperParam(
                type="float", required=True, description="Current period current assets."
            ),
            "current_liabilities": HelperParam(
                type="float", required=True, description="Current period current liabilities."
            ),
            "current_assets_prior": HelperParam(
                type="float", required=True, description="Prior period current assets."
            ),
            "current_liabilities_prior": HelperParam(
                type="float", required=True, description="Prior period current liabilities."
            ),
            "shares_outstanding": HelperParam(
                type="float", required=True, description="Current period shares outstanding."
            ),
            "shares_outstanding_prior": HelperParam(
                type="float", required=True, description="Prior period shares outstanding."
            ),
            "gross_profit": HelperParam(
                type="float", required=True, description="Current period gross profit."
            ),
            "revenue": HelperParam(
                type="float", required=True, description="Current period revenue."
            ),
            "gross_profit_prior": HelperParam(
                type="float", required=True, description="Prior period gross profit."
            ),
            "revenue_prior": HelperParam(
                type="float", required=True, description="Prior period revenue."
            ),
            "total_assets_prior": HelperParam(
                type="float", required=True, description="Prior period total assets."
            ),
            "net_income_prior": HelperParam(
                type="float", required=True, description="Prior period net income."
            ),
        },
        outputs=[
            HelperOutput(
                name="piotroski_f_score",
                type="dict",
                description=(
                    "Dict with f_score (0-9), strength ('strong'/'neutral'/'weak'), "
                    "and criteria breakdown by category."
                ),
            ),
        ],
        produces_artifacts=["ft_piotroski_f_score_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
