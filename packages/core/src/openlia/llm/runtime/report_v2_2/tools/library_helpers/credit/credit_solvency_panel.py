"""credit_solvency_panel — leverage, coverage, and liquidity ratios with implied rating proxy.

Registered name: "credit_solvency_panel"

Per supplement §10:
  - Leverage: Debt/EBITDA, Net Debt/EBITDA, Debt/Equity, Debt/Capital
  - Coverage: EBITDA/Interest, EBIT/Interest, (EBITDA-CapEx)/Interest, fixed-charge, cash
  - Liquidity: Current Ratio, Quick Ratio, Cash/ST Debt
  - Composite credit score (0-100), maps to synthetic rating (AAA through CCC)
  - Multi-year trend interpretation
  - Warnings: Debt/EBITDA > 4x, EBITDA/Interest < 3x, deteriorating trend
  - Optional FRED spread integration: compares implied spread to IG/HY OAS benchmarks
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

# ---------------------------------------------------------------------------
# Implied rating mapping (Damodaran-style, using worst of coverage/leverage)
# ---------------------------------------------------------------------------

# (min_coverage, max_coverage, min_debt_ebitda, max_debt_ebitda, rating)
# Ordered from best to worst; first match wins.
_RATING_TABLE: list[tuple[float, float, float, float, str]] = [
    (12.5, float("inf"), 0.0, 1.0, "AAA"),
    (8.5, 12.5, 1.0, 1.5, "AA"),
    (6.5, 8.5, 1.5, 2.0, "A"),
    (4.5, 6.5, 2.0, 3.0, "BBB"),
    (3.0, 4.5, 3.0, 4.0, "BB"),
    (1.5, 3.0, 4.0, 5.0, "B"),
]
_RATING_CCC = "CCC"

# Credit score lookup per rating (higher = better credit quality)
_RATING_SCORE: dict[str, int] = {
    "AAA": 100,
    "AA": 90,
    "A": 78,
    "BBB": 62,
    "BB": 45,
    "B": 28,
    "CCC": 10,
}


def _implied_rating(coverage_ebit: float | None, debt_to_ebitda: float | None) -> str:
    """Map coverage and leverage to a synthetic rating. Uses the worse of the two."""
    if coverage_ebit is None or debt_to_ebitda is None:
        return "NM"

    for cov_lo, cov_hi, lev_lo, lev_hi, rating in _RATING_TABLE:
        if cov_lo <= coverage_ebit < cov_hi and lev_lo <= debt_to_ebitda < lev_hi:
            return rating

    # CCC or below: coverage < 1.5 OR leverage > 5
    if coverage_ebit < 1.5 or debt_to_ebitda > 5.0:
        return _RATING_CCC

    # Fall-through: mixed signals — use coverage as tiebreaker
    for cov_lo, cov_hi, _lev_lo, _lev_hi, rating in _RATING_TABLE:
        if cov_lo <= coverage_ebit < cov_hi:
            return rating

    return _RATING_CCC


def _credit_score(rating: str) -> int:
    return _RATING_SCORE.get(rating, 0)


def _safe_div(numerator: float | None, denominator: float | None) -> float | str | None:
    """Return numerator/denominator or special values for edge cases."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    result = numerator / denominator
    # Negative denominator can produce misleading ratios; flag separately
    return round(result, 4)


def _trend_direction(series: list[float]) -> str:
    """Return verbal trend from OLS slope over the series."""
    n = len(series)
    if n < 2:
        return "insufficient_data"

    x_mean = (n - 1) / 2.0
    y_mean = sum(series) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(series))
    denom = sum((i - x_mean) ** 2 for i in range(n))
    if denom == 0:
        return "stable"

    slope = num / denom
    # Relative slope: slope / |y_mean|; avoids scale dependency
    if y_mean == 0:
        return "stable"
    rel = slope / abs(y_mean)
    if rel > 0.05:
        return "improving"
    if rel > 0.01:
        return "modest improvement"
    if rel > -0.01:
        return "stable"
    if rel > -0.05:
        return "modest deterioration"
    return "material deterioration"


def _compute_period(
    ebit: float,
    ebitda: float,
    capex: float,
    interest: float,
    op_lease: float,
    total_debt: float,
    cash: float,
    total_equity: float,
    current_assets: float | None,
    current_liabilities: float | None,
    quick_assets: float | None,
    st_debt: float | None,
) -> dict[str, Any]:
    """Compute all credit metrics for a single period."""
    result: dict[str, Any] = {}

    # --- Coverage ---
    if interest > 0:
        result["interest_coverage_ebit"] = round(ebit / interest, 4)
        result["interest_coverage_ebitda"] = round(ebitda / interest, 4)
        result["interest_coverage_ebitda_minus_capex"] = round((ebitda - capex) / interest, 4)
        result["cash_coverage"] = round((ebit + (ebitda - ebit)) / interest, 4)  # = ebitda/int
        # Fixed-charge: (EBIT + lease) / (interest + lease)
        fcc_denom = interest + op_lease
        if fcc_denom > 0:
            result["fixed_charge_coverage"] = round((ebit + op_lease) / fcc_denom, 4)
        else:
            result["fixed_charge_coverage"] = None
    elif interest == 0:
        result["interest_coverage_ebit"] = "infinite"
        result["interest_coverage_ebitda"] = "infinite"
        result["interest_coverage_ebitda_minus_capex"] = "infinite"
        result["cash_coverage"] = "infinite"
        result["fixed_charge_coverage"] = "infinite"
    else:
        # Negative interest (unusual; income from cash)
        result["interest_coverage_ebit"] = None
        result["interest_coverage_ebitda"] = None
        result["interest_coverage_ebitda_minus_capex"] = None
        result["cash_coverage"] = None
        result["fixed_charge_coverage"] = None

    # --- Leverage ---
    if ebitda > 0:
        result["debt_to_ebitda"] = round(total_debt / ebitda, 4)
        net_debt = total_debt - cash
        result["net_debt_to_ebitda"] = round(net_debt / ebitda, 4)
    else:
        result["debt_to_ebitda"] = None
        result["net_debt_to_ebitda"] = None

    if total_equity > 0:
        result["debt_to_equity"] = round(total_debt / total_equity, 4)
        result["debt_to_capital"] = round(total_debt / (total_debt + total_equity), 4)
    elif total_equity < 0:
        result["debt_to_equity"] = "book_insolvent"
        result["debt_to_capital"] = "book_insolvent"
    else:
        result["debt_to_equity"] = None
        result["debt_to_capital"] = None

    # --- Liquidity ---
    if current_assets is not None and current_liabilities is not None and current_liabilities > 0:
        result["current_ratio"] = round(current_assets / current_liabilities, 4)
    else:
        result["current_ratio"] = None

    if quick_assets is not None and current_liabilities is not None and current_liabilities > 0:
        result["quick_ratio"] = round(quick_assets / current_liabilities, 4)
    else:
        result["quick_ratio"] = None

    if st_debt is not None and st_debt > 0:
        result["cash_to_st_debt"] = round(cash / st_debt, 4)
    else:
        result["cash_to_st_debt"] = None

    return result


def execute(
    historical_ebit: list[float],
    historical_ebitda: list[float],
    historical_capex: list[float],
    historical_interest_expense: list[float],
    historical_total_debt: list[float],
    historical_cash: list[float],
    historical_total_equity: list[float],
    historical_total_assets: list[float] | None = None,
    historical_operating_lease_expense: list[float] | None = None,
    historical_current_assets: list[float] | None = None,
    historical_current_liabilities: list[float] | None = None,
    historical_quick_assets: list[float] | None = None,
    historical_st_debt: list[float] | None = None,
    fred_spreads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute credit/solvency panel from time-series financial data.

    Args:
        historical_ebit: EBIT per period, oldest first. Min 4 periods.
        historical_ebitda: EBITDA per period.
        historical_capex: CapEx per period (positive convention).
        historical_interest_expense: Interest expense per period (positive).
        historical_total_debt: Total debt including lease liabilities per period.
        historical_cash: Cash and equivalents per period.
        historical_total_equity: Total book equity per period.
        historical_total_assets: Total assets per period (optional).
        historical_operating_lease_expense: Operating lease expense (optional; zeros default).
        historical_current_assets: Current assets per period (optional; for liquidity).
        historical_current_liabilities: Current liabilities (optional; for liquidity).
        historical_quick_assets: Quick assets = cash + receivables (optional).
        historical_st_debt: Short-term debt per period (optional; for cash/st_debt).
        fred_spreads: Output dict from fred_credit_spreads helper (optional).
            If supplied, derives a ticker-implied spread context vs IG/HY benchmarks.

    Returns:
        Dict with current_period ratios, five_year_trends, trend_interpretation,
        credit_quality_classification, implied_rating_proxy, credit_score,
        fred_spread_context (if supplied), warnings, data_as_of.

    Raises:
        ValueError: If series have fewer than 4 periods or mismatched lengths.
    """
    n = len(historical_ebit)
    if n < 4:
        raise ValueError(f"historical_ebit must have at least 4 periods; got {n}")

    series_map = {
        "historical_ebitda": historical_ebitda,
        "historical_capex": historical_capex,
        "historical_interest_expense": historical_interest_expense,
        "historical_total_debt": historical_total_debt,
        "historical_cash": historical_cash,
        "historical_total_equity": historical_total_equity,
    }
    for name, series in series_map.items():
        if len(series) != n:
            raise ValueError(f"{name} length {len(series)} != historical_ebit length {n}")

    # Pad optional series to length n with None
    op_lease = historical_operating_lease_expense or [0.0] * n
    curr_assets_s = historical_current_assets or [None] * n  # type: ignore[list-item]
    curr_liab_s = historical_current_liabilities or [None] * n  # type: ignore[list-item]
    quick_s = historical_quick_assets or [None] * n  # type: ignore[list-item]
    st_debt_s = historical_st_debt or [None] * n  # type: ignore[list-item]

    # --- Per-period metrics ---
    all_periods: list[dict[str, Any]] = []
    for i in range(n):
        p = _compute_period(
            ebit=historical_ebit[i],
            ebitda=historical_ebitda[i],
            capex=historical_capex[i],
            interest=historical_interest_expense[i],
            op_lease=op_lease[i],
            total_debt=historical_total_debt[i],
            cash=historical_cash[i],
            total_equity=historical_total_equity[i],
            current_assets=curr_assets_s[i],
            current_liabilities=curr_liab_s[i],
            quick_assets=quick_s[i],
            st_debt=st_debt_s[i],
        )
        all_periods.append(p)

    current = all_periods[-1]

    # --- Trends (numeric ratios only) ---
    numeric_keys = [
        "interest_coverage_ebit",
        "interest_coverage_ebitda",
        "interest_coverage_ebitda_minus_capex",
        "debt_to_ebitda",
        "net_debt_to_ebitda",
        "debt_to_equity",
        "debt_to_capital",
    ]

    five_year_trends: dict[str, list[float]] = {}
    trend_interpretation: dict[str, str] = {}
    for key in numeric_keys:
        vals = [p[key] for p in all_periods if isinstance(p.get(key), (int, float))]
        if vals:
            five_year_trends[key] = [round(v, 4) for v in vals]
            trend_interpretation[key] = _trend_direction(vals)

    # --- Implied rating ---
    cov_ebit = current.get("interest_coverage_ebit")
    cov_ebit_float = cov_ebit if isinstance(cov_ebit, float) else None
    d_ebitda = current.get("debt_to_ebitda")
    d_ebitda_float = d_ebitda if isinstance(d_ebitda, float) else None

    rating = _implied_rating(cov_ebit_float, d_ebitda_float)
    score = _credit_score(rating)

    # Map rating to broader quality classification
    _quality_map = {
        "AAA": "investment_grade_strong",
        "AA": "investment_grade_strong",
        "A": "investment_grade_strong",
        "BBB": "investment_grade_adequate",
        "BB": "high_yield",
        "B": "high_yield",
        "CCC": "distressed",
        "NM": "not_meaningful",
    }
    quality_class = _quality_map.get(rating, "not_meaningful")

    # --- Warnings ---
    warnings: list[str] = []
    if d_ebitda_float is not None and d_ebitda_float > 4.0:
        warnings.append(f"Debt/EBITDA {d_ebitda_float:.1f}x exceeds 4x — leverage elevated.")
    if isinstance(cov_ebit, float) and cov_ebit < 3.0:
        warnings.append(f"EBIT interest coverage {cov_ebit:.1f}x below 3x institutional minimum.")
    # Deteriorating coverage trend
    cov_trend = trend_interpretation.get("interest_coverage_ebit", "")
    if "material deterioration" in cov_trend:
        warnings.append("Interest coverage in material deteriorating trend.")
    # Negative equity
    if current.get("debt_to_equity") == "book_insolvent":
        warnings.append("Total equity negative — book insolvent.")

    # --- FRED spread context ---
    fred_context: dict[str, Any] | None = None
    if fred_spreads is not None:
        hy_oas = fred_spreads.get("hy_oas")
        ig_oas = fred_spreads.get("ig_oas")
        as_of = fred_spreads.get("as_of", "")
        fred_context = {
            "hy_oas_pct": hy_oas,
            "ig_oas_pct": ig_oas,
            "as_of": as_of,
            "implied_category": quality_class,
            "benchmark_spread_applicable": ig_oas
            if quality_class.startswith("investment_grade")
            else hy_oas,
            "interpretation": (
                f"Implied {rating} (proxy) maps to {quality_class}. "
                + (
                    f"Current IG OAS benchmark: {ig_oas}% as of {as_of}."
                    if quality_class.startswith("investment_grade")
                    else f"Current HY OAS benchmark: {hy_oas}% as of {as_of}."
                )
            ),
        }

    result: dict[str, Any] = {
        "current_period": current,
        "five_year_trends": five_year_trends,
        "trend_interpretation": trend_interpretation,
        "credit_quality_classification": quality_class,
        "implied_rating_proxy": f"{rating} (proxy - not an actual rating)",
        "credit_score": score,
        "warnings": warnings,
    }
    if fred_context is not None:
        result["fred_spread_context"] = fred_context

    return result


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="credit_solvency_panel",
        category=Category.FORENSIC,
        one_liner="Leverage, coverage, and liquidity ratios with implied rating proxy (AAA-CCC).",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute a full credit/solvency panel: EBIT and EBITDA interest coverage, "
            "fixed-charge coverage, debt/EBITDA, debt/equity, debt/capital, current ratio, "
            "quick ratio, and cash/ST debt. Derives an implied synthetic rating (AAA-CCC) and "
            "credit score (0-100). Detects leverage warnings (Debt/EBITDA > 4x) and coverage "
            "warnings (EBITDA/Interest < 3x). Optional FRED spread context."
        ),
        when_to_use=[
            "Credit framing section of any initiation or update report with material debt.",
            "Cross-company leverage comparison in sector reports.",
            "Detecting deteriorating coverage trends over time.",
        ],
        when_not_to_use=[
            "Banks or insurers — specialized credit metrics (CET1, NCO) apply.",
            "Development-stage pre-revenue companies with no meaningful debt service.",
            "As a standalone hard verdict — pair with altman_z_variants for distress probability.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "historical_ebit": HelperParam(
                type="list[float]",
                required=True,
                description="EBIT per period, oldest first. Min 4 periods.",
            ),
            "historical_ebitda": HelperParam(
                type="list[float]",
                required=True,
                description="EBITDA per period, oldest first.",
            ),
            "historical_capex": HelperParam(
                type="list[float]",
                required=True,
                description="CapEx per period (positive convention).",
            ),
            "historical_interest_expense": HelperParam(
                type="list[float]",
                required=True,
                description="Interest expense per period (positive).",
            ),
            "historical_total_debt": HelperParam(
                type="list[float]",
                required=True,
                description="Total debt including operating lease liabilities.",
            ),
            "historical_cash": HelperParam(
                type="list[float]",
                required=True,
                description="Cash and equivalents per period.",
            ),
            "historical_total_equity": HelperParam(
                type="list[float]",
                required=True,
                description="Total book equity per period.",
            ),
            "historical_total_assets": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Total assets per period (optional).",
            ),
            "historical_operating_lease_expense": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Operating lease expense for fixed-charge coverage. Defaults to zeros.",
            ),
            "historical_current_assets": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Current assets for current ratio (optional).",
            ),
            "historical_current_liabilities": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Current liabilities for current and quick ratios (optional).",
            ),
            "historical_quick_assets": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Cash + receivables for quick ratio (optional).",
            ),
            "historical_st_debt": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Short-term debt for cash/ST debt ratio (optional).",
            ),
            "fred_spreads": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Output dict from fred_credit_spreads helper. "
                    "If provided, appends spread context vs IG/HY OAS benchmarks."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="credit_solvency_output",
                type="credit_solvency_output",
                description=(
                    "current_period dict with all 9+ ratios, five_year_trends, "
                    "trend_interpretation, credit_quality_classification, "
                    "implied_rating_proxy (with disclaimer), credit_score (0-100), "
                    "optional fred_spread_context, warnings list."
                ),
            ),
        ],
        produces_artifacts=["credit_solvency_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
