"""five_step_dupont - 5-step DuPont ROE decomposition.

Registered name: "five_step_dupont"

Per supplement §11:
  ROE = (NI/EBT) x (EBT/EBIT) x (EBIT/Sales) x (Sales/Assets) x (Assets/Equity)
      = tax_burden x interest_burden x operating_margin x asset_turnover x equity_multiplier

Also computes 3-step DuPont:
  ROE = NI_margin x asset_turnover x equity_multiplier

Five-year change decomposition and per-component trend.
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

_TOLERANCE = 0.005  # 0.5% tolerance for numeric consistency check


def _dupont5(
    ni: float,
    ebt: float,
    ebit: float,
    sales: float,
    total_assets: float,
    total_equity: float,
) -> dict[str, float]:
    """Compute 5-step DuPont components for a single period.

    Returns dict with all 5 factors and the derived ROE.

    Raises:
        ValueError: For structurally invalid inputs (zero denominators, negative equity).
    """
    if total_equity <= 0:
        raise ValueError(f"total_equity must be positive for DuPont; got {total_equity}")
    if sales == 0:
        raise ValueError("sales must be non-zero for DuPont (asset turnover undefined)")
    if ebit == 0:
        raise ValueError("ebit must be non-zero for DuPont (interest burden undefined)")
    if ebt == 0:
        raise ValueError("ebt must be non-zero for DuPont (tax burden undefined)")

    tax_burden = ni / ebt
    interest_burden = ebt / ebit
    operating_margin = ebit / sales
    asset_turnover = sales / total_assets
    equity_multiplier = total_assets / total_equity

    roe_product = (
        tax_burden * interest_burden * operating_margin * asset_turnover * equity_multiplier
    )

    return {
        "tax_burden": round(tax_burden, 6),
        "interest_burden": round(interest_burden, 6),
        "operating_margin": round(operating_margin, 6),
        "asset_turnover": round(asset_turnover, 6),
        "equity_multiplier": round(equity_multiplier, 6),
        "roe": round(roe_product, 6),
    }


def _dupont3(
    ni: float,
    sales: float,
    total_assets: float,
    total_equity: float,
) -> dict[str, float]:
    """Compute 3-step DuPont for a single period."""
    if total_equity <= 0:
        raise ValueError("total_equity must be positive for 3-step DuPont")
    if sales == 0:
        raise ValueError("sales must be non-zero for 3-step DuPont")

    ni_margin = ni / sales
    asset_turnover = sales / total_assets
    equity_multiplier = total_assets / total_equity
    roe_3 = ni_margin * asset_turnover * equity_multiplier

    return {
        "ni_margin": round(ni_margin, 6),
        "asset_turnover": round(asset_turnover, 6),
        "equity_multiplier": round(equity_multiplier, 6),
        "roe": round(roe_3, 6),
    }


def _decompose_roe_change(
    components_t0: dict[str, float],
    components_t1: dict[str, float],
) -> dict[str, Any]:
    """Approximate additive decomposition of ROE change across 5 drivers.

    Uses log-difference decomposition:
      dROE approx ROE_t1 x sum(d_factor_i / factor_i_t0)

    Returns per-driver contribution in absolute ROE points and an interpretation.
    """
    roe_t0 = components_t0["roe"]
    roe_t1 = components_t1["roe"]
    delta_roe = roe_t1 - roe_t0

    factors = [
        "tax_burden",
        "interest_burden",
        "operating_margin",
        "asset_turnover",
        "equity_multiplier",
    ]
    contributions: dict[str, float] = {}
    for f in factors:
        v0 = components_t0[f]
        v1 = components_t1[f]
        if v0 != 0:
            # Multiplicative log contribution
            contrib = roe_t1 * ((v1 - v0) / v0)
        else:
            contrib = 0.0
        contributions[f] = round(contrib, 6)

    # Quality interpretation
    op_contrib = contributions.get("operating_margin", 0)
    at_contrib = contributions.get("asset_turnover", 0)
    em_contrib = contributions.get("equity_multiplier", 0)
    quality_drivers = op_contrib + at_contrib
    leverage_drivers = em_contrib

    if delta_roe > 0 and quality_drivers > 0.6 * delta_roe:
        interpretation = (
            f"ROE +{delta_roe * 100:.1f} pts; high-quality improvement (margin + turnover driven)."
        )
    elif delta_roe > 0 and leverage_drivers > 0.5 * delta_roe:
        interpretation = f"ROE +{delta_roe * 100:.1f} pts; primarily leverage-driven improvement."
    elif delta_roe < 0:
        interpretation = f"ROE {delta_roe * 100:.1f} pts; deterioration over the period."
    else:
        interpretation = f"ROE change {delta_roe * 100:.1f} pts; mixed drivers."

    return {
        "total": round(delta_roe, 6),
        "drivers": contributions,
        "interpretation": interpretation,
    }


def execute(
    historical_net_income: list[float],
    historical_ebt: list[float],
    historical_ebit: list[float],
    historical_sales: list[float],
    historical_total_assets: list[float],
    historical_total_equity: list[float],
) -> dict[str, Any]:
    """Compute 5-step DuPont decomposition from time-series financials.

    Args:
        historical_net_income: Net income per period, oldest first. Min 5 periods.
        historical_ebt: Pre-tax income (EBT) per period.
        historical_ebit: Earnings before interest and taxes per period.
        historical_sales: Net revenue per period.
        historical_total_assets: Total assets per period.
        historical_total_equity: Total book equity per period.

    Returns:
        Dict with:
          - decomposition: per-factor time series
          - current_period: most recent period values
          - three_step: 3-step DuPont per period and current
          - five_year_change_in_roe: total ΔROE and per-driver contributions
          - errors: list of periods where computation failed
          - narrative: ~2-sentence interpretation

    Raises:
        ValueError: If fewer than 5 periods or series length mismatch.
    """
    n = len(historical_net_income)
    if n < 5:
        raise ValueError(f"historical_net_income must have at least 5 periods; got {n}")

    series_names = {
        "historical_ebt": historical_ebt,
        "historical_ebit": historical_ebit,
        "historical_sales": historical_sales,
        "historical_total_assets": historical_total_assets,
        "historical_total_equity": historical_total_equity,
    }
    for name, series in series_names.items():
        if len(series) != n:
            raise ValueError(f"{name} length {len(series)} != historical_net_income length {n}")

    # --- Compute per-period ---
    five_factors: list[str] = [
        "tax_burden",
        "interest_burden",
        "operating_margin",
        "asset_turnover",
        "equity_multiplier",
        "roe",
    ]
    three_factors: list[str] = ["ni_margin", "asset_turnover", "equity_multiplier", "roe"]

    decomp_5: dict[str, list[float | None]] = {f: [] for f in five_factors}
    decomp_3: dict[str, list[float | None]] = {f: [] for f in three_factors}
    errors: list[dict[str, Any]] = []
    valid_5: list[dict[str, float]] = []

    for i in range(n):
        try:
            r5 = _dupont5(
                ni=historical_net_income[i],
                ebt=historical_ebt[i],
                ebit=historical_ebit[i],
                sales=historical_sales[i],
                total_assets=historical_total_assets[i],
                total_equity=historical_total_equity[i],
            )
            for f in five_factors:
                decomp_5[f].append(r5[f])
            valid_5.append(r5)
        except ValueError as exc:
            for f in five_factors:
                decomp_5[f].append(None)
            errors.append({"period_index": i, "reason": str(exc)})
            valid_5.append({})

        try:
            r3 = _dupont3(
                ni=historical_net_income[i],
                sales=historical_sales[i],
                total_assets=historical_total_assets[i],
                total_equity=historical_total_equity[i],
            )
            for f in three_factors:
                decomp_3[f].append(r3[f])
        except ValueError:
            for f in three_factors:
                decomp_3[f].append(None)

    # Refuse entirely if ALL periods failed (e.g., all-negative equity)
    if len(errors) == n:
        first_reason = errors[0]["reason"] if errors else "unknown"
        raise ValueError(
            f"DuPont computation failed for all {n} periods. First error: {first_reason}"
        )

    # --- Current period ---
    current = {f: decomp_5[f][-1] for f in five_factors}
    current_3 = {f: decomp_3[f][-1] for f in three_factors}

    # --- Five-year change decomposition ---
    roe_change: dict[str, Any] = {}
    # Use oldest and newest valid 5-factor periods
    valid_indices = [i for i, v in enumerate(valid_5) if v]
    if len(valid_indices) >= 2:
        oldest = valid_5[valid_indices[0]]
        newest = valid_5[valid_indices[-1]]
        if oldest and newest:
            roe_change = _decompose_roe_change(oldest, newest)

    # --- Narrative ---
    cp = {f: current[f] for f in five_factors if current[f] is not None}
    if cp:
        roe_val = cp.get("roe", 0) * 100
        om_val = cp.get("operating_margin", 0) * 100
        at_val = cp.get("asset_turnover", 0)
        em_val = cp.get("equity_multiplier", 0)
        narrative = (
            f"Five-step DuPont: ROE {roe_val:.1f}% built on "
            f"{om_val:.1f}% operating margin, {at_val:.2f}x asset turnover, "
            f"{em_val:.2f}x leverage."
        )
        if roe_change.get("interpretation"):
            narrative += " " + roe_change["interpretation"]
    else:
        narrative = "DuPont computation not possible for the current period — check input data."

    return {
        "decomposition": decomp_5,
        "current_period": current,
        "three_step": {
            "decomposition": decomp_3,
            "current_period": current_3,
        },
        "five_year_change_in_roe": roe_change,
        "errors": errors,
        "narrative": narrative,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="five_step_dupont",
        category=Category.FORENSIC,
        one_liner="5-step DuPont ROE: tax burden, interest burden, margin, turnover, leverage.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Decompose ROE into five drivers: tax_burden x interest_burden x "
            "operating_margin x asset_turnover x equity_multiplier. "
            "Also produces 3-step DuPont and a five-year ROE change decomposition "
            "with per-driver contributions. Identifies whether ROE improvement is "
            "high-quality (margin + turnover) or leverage-driven."
        ),
        when_to_use=[
            "Return-on-capital deep dives in initiation or update reports.",
            "Cross-company ROE composition comparison in sector analysis.",
            "Identifying whether management improved quality or simply levered up.",
        ],
        when_not_to_use=[
            "Negative equity companies; equity multiplier is undefined.",
            "Pre-revenue development-stage companies with zero or negative sales.",
            "Single-period snapshot only; requires at least 5 years for trend.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "historical_net_income": HelperParam(
                type="list[float]",
                required=True,
                description="Net income per period, oldest first. Min 5 periods.",
            ),
            "historical_ebt": HelperParam(
                type="list[float]",
                required=True,
                description="Pre-tax income (EBT) per period.",
            ),
            "historical_ebit": HelperParam(
                type="list[float]",
                required=True,
                description="EBIT per period.",
            ),
            "historical_sales": HelperParam(
                type="list[float]",
                required=True,
                description="Net revenue per period.",
            ),
            "historical_total_assets": HelperParam(
                type="list[float]",
                required=True,
                description="Total assets per period.",
            ),
            "historical_total_equity": HelperParam(
                type="list[float]",
                required=True,
                description="Total book equity per period.",
            ),
        },
        outputs=[
            HelperOutput(
                name="five_step_dupont_output",
                type="five_step_dupont_output",
                description=(
                    "decomposition dict with per-factor time series, current_period, "
                    "three_step decomposition, five_year_change_in_roe with per-driver "
                    "contributions, errors list, narrative."
                ),
            ),
        ],
        produces_artifacts=["five_step_dupont_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
