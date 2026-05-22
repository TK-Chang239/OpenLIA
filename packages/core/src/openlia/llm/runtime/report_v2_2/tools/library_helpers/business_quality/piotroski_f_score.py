"""piotroski_f_score — 9-point Piotroski F-Score with DROA audit fix (full-year YoY).

Registered name: "piotroski_f_score"

Audit fix §9.2: DROA uses full-year YoY delta (not quarterly). This helper
is distinct from ft_piotroski_f_score which wraps FinanceToolkit. This version
applies the DROA audit fix explicitly and does not rely on the FT library.

The 9 criteria:
  Profitability (4):
    F1. ROA > 0
    F2. CFO > 0
    F3. DROA > 0 [audit fix: full-year delta ROA]
    F4. Accruals: CFO/Assets > ROA (quality)
  Leverage/Liquidity (3):
    F5. Change in leverage < 0 (leverage improved)
    F6. Change in current ratio > 0 (liquidity improved)
    F7. No new shares issued
  Operating Efficiency (2):
    F8. Gross margin improved YoY
    F9. Asset turnover improved YoY
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
    # Current year (full-year)
    net_income: float,
    total_assets: float,
    operating_cash_flow: float,
    total_debt: float,
    current_assets: float,
    current_liabilities: float,
    gross_profit: float,
    revenue: float,
    shares_outstanding: float,
    # Prior full year (audit fix §9.2: full-year comparison)
    net_income_prior: float,
    total_assets_prior: float,
    total_debt_prior: float,
    current_assets_prior: float,
    current_liabilities_prior: float,
    gross_profit_prior: float,
    revenue_prior: float,
    shares_outstanding_prior: float,
) -> dict[str, Any]:
    """Compute Piotroski F-Score with full-year DROA audit fix.

    ROA = net_income / total_assets (full-year figures only).
    DROA = ROA_current - ROA_prior (full-year YoY; audit fix §9.2).

    Returns:
        Dict with f_score (0-9), strength, and per-criterion breakdown.
    """
    if total_assets == 0 or total_assets_prior == 0:
        raise ValueError("total_assets and total_assets_prior must be non-zero")

    # --- Profitability signals ---
    roa = net_income / total_assets
    roa_prior = net_income_prior / total_assets_prior

    f1_roa_positive = int(roa > 0)
    f2_cfo_positive = int(operating_cash_flow > 0)
    # F3: DROA > 0 using FULL-YEAR delta (audit fix §9.2)
    f3_delta_roa_positive = int(roa > roa_prior)
    # F4: accruals = CFO/assets > ROA (cash-backed earnings)
    f4_accruals = int(operating_cash_flow / total_assets > roa)

    # --- Leverage/Liquidity signals ---
    leverage = total_debt / total_assets
    leverage_prior = total_debt_prior / total_assets_prior
    f5_leverage_decreased = int(leverage < leverage_prior)

    cr = current_assets / current_liabilities if current_liabilities != 0 else 0.0
    cr_prior = (
        current_assets_prior / current_liabilities_prior if current_liabilities_prior != 0 else 0.0
    )
    f6_current_ratio_improved = int(cr > cr_prior)

    f7_no_dilution = int(shares_outstanding <= shares_outstanding_prior)

    # --- Operating Efficiency signals ---
    gross_margin = gross_profit / revenue if revenue != 0 else 0.0
    gross_margin_prior = gross_profit_prior / revenue_prior if revenue_prior != 0 else 0.0
    f8_gross_margin_improved = int(gross_margin > gross_margin_prior)

    asset_turnover = revenue / total_assets
    asset_turnover_prior = revenue_prior / total_assets_prior
    f9_asset_turnover_improved = int(asset_turnover > asset_turnover_prior)

    f_score = (
        f1_roa_positive
        + f2_cfo_positive
        + f3_delta_roa_positive
        + f4_accruals
        + f5_leverage_decreased
        + f6_current_ratio_improved
        + f7_no_dilution
        + f8_gross_margin_improved
        + f9_asset_turnover_improved
    )

    strength = "strong" if f_score >= 8 else ("neutral" if f_score >= 5 else "weak")

    return {
        "f_score": f_score,
        "strength": strength,
        "roa": round(roa, 4),
        "roa_prior": round(roa_prior, 4),
        "delta_roa": round(roa - roa_prior, 4),
        "criteria": {
            "profitability": {
                "F1_roa_positive": f1_roa_positive,
                "F2_cfo_positive": f2_cfo_positive,
                "F3_delta_roa_positive_full_year": f3_delta_roa_positive,
                "F4_accruals_low": f4_accruals,
            },
            "leverage_liquidity": {
                "F5_leverage_decreased": f5_leverage_decreased,
                "F6_current_ratio_improved": f6_current_ratio_improved,
                "F7_no_dilution": f7_no_dilution,
            },
            "operating_efficiency": {
                "F8_gross_margin_improved": f8_gross_margin_improved,
                "F9_asset_turnover_improved": f9_asset_turnover_improved,
            },
        },
        "audit_note": "DROA uses full-year YoY comparison per audit fix §9.2",
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="piotroski_f_score",
        category=Category.BUSINESS_QUALITY,
        one_liner="9-point Piotroski F-Score with full-year YoY DROA (audit fix §9.2).",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the Piotroski F-Score using full-year annual data only (not quarterly). "
            "Applies audit fix §9.2: DROA = full-year ROA_current - full-year ROA_prior. "
            "Use instead of ft_piotroski_f_score when audit-corrected DROA is required."
        ),
        when_to_use=[
            "Fundamental quality screening in equity research with annual data.",
            "When audit-corrected DROA (full-year, not quarterly) is needed.",
        ],
        when_not_to_use=[
            "Quarterly data — this helper requires full-year figures for DROA.",
            "Altman Z-Score distress prediction — use ft_altman_z_score.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "net_income": HelperParam(
                type="float", required=True, description="Full-year net income."
            ),
            "total_assets": HelperParam(
                type="float", required=True, description="Full-year total assets."
            ),
            "operating_cash_flow": HelperParam(
                type="float", required=True, description="Full-year OCF."
            ),
            "total_debt": HelperParam(
                type="float", required=True, description="Full-year total debt."
            ),
            "current_assets": HelperParam(
                type="float", required=True, description="Current assets."
            ),
            "current_liabilities": HelperParam(
                type="float", required=True, description="Current liabilities."
            ),
            "gross_profit": HelperParam(
                type="float", required=True, description="Full-year gross profit."
            ),
            "revenue": HelperParam(type="float", required=True, description="Full-year revenue."),
            "shares_outstanding": HelperParam(
                type="float", required=True, description="Current shares."
            ),
            "net_income_prior": HelperParam(
                type="float", required=True, description="Prior full-year net income."
            ),
            "total_assets_prior": HelperParam(
                type="float", required=True, description="Prior full-year total assets."
            ),
            "total_debt_prior": HelperParam(
                type="float", required=True, description="Prior full-year total debt."
            ),
            "current_assets_prior": HelperParam(
                type="float", required=True, description="Prior current assets."
            ),
            "current_liabilities_prior": HelperParam(
                type="float", required=True, description="Prior current liabilities."
            ),
            "gross_profit_prior": HelperParam(
                type="float", required=True, description="Prior gross profit."
            ),
            "revenue_prior": HelperParam(type="float", required=True, description="Prior revenue."),
            "shares_outstanding_prior": HelperParam(
                type="float", required=True, description="Prior shares."
            ),
        },
        outputs=[
            HelperOutput(
                name="piotroski_f_score",
                type="dict",
                description=(
                    "f_score (0-9), strength, roa, roa_prior, delta_roa, "
                    "criteria breakdown by pillar, audit_note."
                ),
            ),
        ],
        produces_artifacts=["piotroski_f_score_output"],
        consumes_artifacts=[],
    ),
)

register_helper(_SCHEMA, execute)
