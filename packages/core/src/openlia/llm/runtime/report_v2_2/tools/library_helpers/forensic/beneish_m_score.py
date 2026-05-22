"""beneish_m_score — Earnings manipulation red-flag detector (Beneish 1999).

Registered name: "beneish_m_score"

8-variable model:
  DSRI  Days Sales Receivable Index
  GMI   Gross Margin Index
  AQI   Asset Quality Index
  SGI   Sales Growth Index
  DEPI  Depreciation Index
  SGAI  SG&A Index
  LVGI  Leverage Index
  TATA  Total Accruals to Total Assets (NI - CFO proxy)

M-score = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI
          + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

Threshold: M-score > -1.78 -> likely manipulator.

Per helpers-design §4.18.
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
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# M-score intercept and coefficients
_INTERCEPT = -4.84
_COEFFICIENTS = {
    "DSRI": 0.92,
    "GMI": 0.528,
    "AQI": 0.404,
    "SGI": 0.892,
    "DEPI": 0.115,
    "SGAI": -0.172,
    "TATA": 4.679,
    "LVGI": -0.327,
}

_THRESHOLD = -1.78


def execute(
    accounts_receivable_t: float,
    accounts_receivable_t1: float,
    revenue_t: float,
    revenue_t1: float,
    gross_profit_t: float,
    gross_profit_t1: float,
    current_assets_t: float,
    current_assets_t1: float,
    ppe_t: float,
    ppe_t1: float,
    total_assets_t: float,
    total_assets_t1: float,
    depreciation_t: float,
    depreciation_t1: float,
    sga_t: float,
    sga_t1: float,
    total_debt_t: float,
    total_debt_t1: float,
    net_income_t: float,
    cfo_t: float,
) -> dict[str, Any]:
    """Compute the Beneish M-score.

    All inputs are current-period (_t) and prior-period (_t1) annual figures.

    Args:
        accounts_receivable_t: Accounts receivable, current period.
        accounts_receivable_t1: Accounts receivable, prior period.
        revenue_t: Net revenue, current period.
        revenue_t1: Net revenue, prior period.
        gross_profit_t: Gross profit, current period.
        gross_profit_t1: Gross profit, prior period.
        current_assets_t: Current assets, current period.
        current_assets_t1: Current assets, prior period.
        ppe_t: Net PP&E, current period.
        ppe_t1: Net PP&E, prior period.
        total_assets_t: Total assets, current period.
        total_assets_t1: Total assets, prior period.
        depreciation_t: Depreciation expense, current period.
        depreciation_t1: Depreciation expense, prior period.
        sga_t: SG&A expense, current period.
        sga_t1: SG&A expense, prior period.
        total_debt_t: Total debt (short + long term), current period.
        total_debt_t1: Total debt, prior period.
        net_income_t: Net income, current period.
        cfo_t: Cash from operations, current period.
            Used for TATA via NI - CFO proxy.

    Returns:
        Dict with m_score, threshold, verdict, all 8 sub-indices,
        and classification ("likely_manipulator" / "no_signal").

    Raises:
        ValueError: If any denominator required for ratio computation is zero.
    """
    warnings_list: list[str] = []

    def _safe_div(num: float, denom: float, label: str) -> float:
        if denom == 0:
            raise ValueError(f"Denominator is zero for {label}")
        return num / denom

    # --- DSRI: Days Sales Receivable Index ---
    # (AR_t / Rev_t) / (AR_t1 / Rev_t1)
    dsr_t = _safe_div(accounts_receivable_t, revenue_t, "DSR_t (AR_t/Rev_t)")
    dsr_t1 = _safe_div(accounts_receivable_t1, revenue_t1, "DSR_t1 (AR_t1/Rev_t1)")
    dsri = _safe_div(dsr_t, dsr_t1, "DSRI (DSR_t / DSR_t1)")

    # --- GMI: Gross Margin Index ---
    # GM_t1 / GM_t  (inverted — prior / current)
    gm_t = _safe_div(gross_profit_t, revenue_t, "GM_t")
    gm_t1 = _safe_div(gross_profit_t1, revenue_t1, "GM_t1")
    gmi = _safe_div(gm_t1, gm_t, "GMI (GM_t1 / GM_t)")

    # --- AQI: Asset Quality Index ---
    # (1 - (CA_t + PPE_t) / TA_t) / (1 - (CA_t1 + PPE_t1) / TA_t1)
    aq_t = 1.0 - _safe_div(current_assets_t + ppe_t, total_assets_t, "AQ_t")
    aq_t1 = 1.0 - _safe_div(current_assets_t1 + ppe_t1, total_assets_t1, "AQ_t1")
    if aq_t1 == 0:
        raise ValueError("AQI denominator (aq_t1) is zero")
    aqi = aq_t / aq_t1

    # --- SGI: Sales Growth Index ---
    # Rev_t / Rev_t1
    sgi = _safe_div(revenue_t, revenue_t1, "SGI (Rev_t / Rev_t1)")

    # --- DEPI: Depreciation Index ---
    # (Dep_t1 / (Dep_t1 + PPE_t1)) / (Dep_t / (Dep_t + PPE_t))
    dep_rate_t1 = _safe_div(depreciation_t1, depreciation_t1 + ppe_t1, "DEPI dep_rate_t1")
    dep_rate_t = _safe_div(depreciation_t, depreciation_t + ppe_t, "DEPI dep_rate_t")
    if dep_rate_t == 0:
        raise ValueError("DEPI denominator (dep_rate_t) is zero")
    depi = dep_rate_t1 / dep_rate_t

    # --- SGAI: Sales, General & Admin Index ---
    # (SGA_t / Rev_t) / (SGA_t1 / Rev_t1)
    sga_ratio_t = _safe_div(sga_t, revenue_t, "SGAI sga_ratio_t")
    sga_ratio_t1 = _safe_div(sga_t1, revenue_t1, "SGAI sga_ratio_t1")
    if sga_ratio_t1 == 0:
        raise ValueError("SGAI denominator (sga_ratio_t1) is zero")
    sgai = sga_ratio_t / sga_ratio_t1

    # --- LVGI: Leverage Index ---
    # (TotalDebt_t / TA_t) / (TotalDebt_t1 / TA_t1)
    lev_t = _safe_div(total_debt_t, total_assets_t, "LVGI lev_t")
    lev_t1 = _safe_div(total_debt_t1, total_assets_t1, "LVGI lev_t1")
    if lev_t1 == 0:
        # No prior debt — LVGI undefined; flag and default to 1.0
        warnings_list.append("Prior-period leverage is zero; LVGI defaulted to 1.0")
        lvgi = 1.0
    else:
        lvgi = lev_t / lev_t1

    # --- TATA: Total Accruals to Total Assets ---
    # (NI - CFO) / TA_t  [modern cash-flow proxy; Beneish 1999 original uses BS delta]
    tata = _safe_div(net_income_t - cfo_t, total_assets_t, "TATA")
    warnings_list.append(
        "TATA uses NI - CFO proxy (modern convention). "
        "Beneish 1999 original uses balance-sheet working-capital delta; "
        "verify if material to thesis."
    )

    # --- M-score ---
    indices = {
        "DSRI": dsri,
        "GMI": gmi,
        "AQI": aqi,
        "SGI": sgi,
        "DEPI": depi,
        "SGAI": sgai,
        "LVGI": lvgi,
        "TATA": tata,
    }

    m_score = _INTERCEPT
    contributions: dict[str, float] = {}
    for name, coef in _COEFFICIENTS.items():
        contrib = coef * indices[name]
        contributions[name] = round(contrib, 6)
        m_score += contrib

    m_score = round(m_score, 4)
    likely_manipulator = m_score > _THRESHOLD
    classification = "likely_manipulator" if likely_manipulator else "no_signal"
    verdict = (
        f"M-score {m_score:.3f} > {_THRESHOLD} threshold — likely manipulator"
        if likely_manipulator
        else f"M-score {m_score:.3f} <= {_THRESHOLD} threshold; no manipulation signal"
    )

    if likely_manipulator:
        warnings_list.append(
            f"M-score {m_score:.3f} exceeds manipulation threshold {_THRESHOLD}. "
            "Investigate the largest contributing indices."
        )

    # Top 3 contributing indices by absolute weighted contribution
    top_drivers = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:3]

    return {
        "m_score": m_score,
        "threshold": _THRESHOLD,
        "verdict": verdict,
        "classification": classification,
        "components": {name: round(v, 6) for name, v in indices.items()},
        "weighted_contributions": contributions,
        "top_drivers": [{"index": k, "contribution": round(v, 4)} for k, v in top_drivers],
        "warnings": warnings_list,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="beneish_m_score",
        category=Category.FORENSIC,
        one_liner="Beneish M-score: 8-index earnings manipulation detector (threshold -1.78).",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the Beneish M-score to detect potential earnings manipulation. "
            "Produces all 8 sub-indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA), "
            "the composite M-score, and a classification vs. the -1.78 threshold."
        ),
        when_to_use=[
            "Forensic audit step before drafting any earnings quality section.",
            "When revenue or AR growth significantly outpaces cash flow.",
            "Cross-company manipulation screening in a sector report.",
        ],
        when_not_to_use=[
            "Banks or insurers — balance sheet structure invalidates several indices.",
            "Companies with < 2 years of reported financials — requires two periods.",
            "As a standalone verdict — corroborate with cross_statement_validation"
            " or quality_of_earnings_panel before drawing conclusions.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "accounts_receivable_t": HelperParam(
                type="float", required=True, description="AR, current period."
            ),
            "accounts_receivable_t1": HelperParam(
                type="float", required=True, description="AR, prior period."
            ),
            "revenue_t": HelperParam(
                type="float", required=True, description="Net revenue, current period."
            ),
            "revenue_t1": HelperParam(
                type="float", required=True, description="Net revenue, prior period."
            ),
            "gross_profit_t": HelperParam(
                type="float", required=True, description="Gross profit, current period."
            ),
            "gross_profit_t1": HelperParam(
                type="float", required=True, description="Gross profit, prior period."
            ),
            "current_assets_t": HelperParam(
                type="float", required=True, description="Current assets, current period."
            ),
            "current_assets_t1": HelperParam(
                type="float", required=True, description="Current assets, prior period."
            ),
            "ppe_t": HelperParam(
                type="float", required=True, description="Net PP&E, current period."
            ),
            "ppe_t1": HelperParam(
                type="float", required=True, description="Net PP&E, prior period."
            ),
            "total_assets_t": HelperParam(
                type="float", required=True, description="Total assets, current period."
            ),
            "total_assets_t1": HelperParam(
                type="float", required=True, description="Total assets, prior period."
            ),
            "depreciation_t": HelperParam(
                type="float", required=True, description="Depreciation expense, current period."
            ),
            "depreciation_t1": HelperParam(
                type="float", required=True, description="Depreciation expense, prior period."
            ),
            "sga_t": HelperParam(
                type="float", required=True, description="SG&A expense, current period."
            ),
            "sga_t1": HelperParam(
                type="float", required=True, description="SG&A expense, prior period."
            ),
            "total_debt_t": HelperParam(
                type="float", required=True, description="Total debt, current period."
            ),
            "total_debt_t1": HelperParam(
                type="float", required=True, description="Total debt, prior period."
            ),
            "net_income_t": HelperParam(
                type="float", required=True, description="Net income, current period."
            ),
            "cfo_t": HelperParam(
                type="float",
                required=True,
                description=(
                    "Cash from operations, current period. "
                    "Used for TATA = (NI - CFO) / TA (modern proxy)."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="beneish_m_score_output",
                type="beneish_m_score_output",
                description=(
                    "m_score, threshold (-1.78), verdict, classification "
                    "(likely_manipulator / no_signal), 8 component indices, "
                    "weighted contributions, top_drivers list, warnings."
                ),
            ),
        ],
        produces_artifacts=["beneish_m_score_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
