"""ddm_family — dividend discount model family (Gordon, two-stage, three-stage, H-model).

Registered name: "ddm_family"

Four DDM variants for valuing dividend-paying equities:
  "gordon"      — constant-growth perpetuity: P = D1 / (Re - g)
  "two_stage"   — explicit high-growth phase + stable perpetuity
  "three_stage" — high-growth + linear-fade transition + stable perpetuity
  "h_model"     — Fuller-Hsia simplified linear fade (H = half-life in years)
  "all"         — run all applicable models and return each result

Sustainability check: if implied payout * (1 + stage1_growth) > net income per share,
flag as potentially unsustainable. Reported, not a hard block.

Design ref: planning/2026-05-22-helpers-design-supplement.md §4
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Core math helpers
# ---------------------------------------------------------------------------


def _gordon(d0: float, re: float, g: float) -> dict[str, Any]:
    """Single-stage Gordon growth model."""
    if re <= g:
        raise ValueError(
            f"cost_of_equity ({re}) must be > growth ({g}). "
            "Gordon growth formula diverges when Re <= g."
        )
    d1 = d0 * (1.0 + g)
    price = d1 / (re - g)
    return {
        "price_per_share": price,
        "pv_breakdown": {"perpetuity": price},
        "stages": [{"label": "perpetuity", "growth_rate": g}],
    }


def _two_stage(
    d0: float,
    re: float,
    g_high: float,
    n_high: int,
    g_stable: float,
) -> dict[str, Any]:
    """Two-stage DDM: explicit high-growth phase + Gordon perpetuity."""
    if re <= g_stable:
        raise ValueError(f"cost_of_equity ({re}) must be > g_stable ({g_stable}).")
    if re <= g_high:
        raise ValueError(
            f"cost_of_equity ({re}) must be > g_high ({g_high}) for the "
            "explicit-period phase to produce finite PVs."
        )

    # Stage 1: PV of explicit dividends
    pv_explicit = 0.0
    dividends: list[float] = []
    d_t = d0
    for t in range(1, n_high + 1):
        d_t = d_t * (1.0 + g_high)
        dividends.append(d_t)
        pv_explicit += d_t / (1.0 + re) ** t

    # Stage 2: Gordon perpetuity starting at end of high-growth phase
    d_n1_plus_1 = d_t * (1.0 + g_stable)  # first dividend in perpetuity phase
    tv_nominal = d_n1_plus_1 / (re - g_stable)
    pv_tv = tv_nominal / (1.0 + re) ** n_high

    price = pv_explicit + pv_tv

    return {
        "price_per_share": price,
        "pv_breakdown": {
            "stage1_explicit": pv_explicit,
            "stage2_terminal": pv_tv,
        },
        "stages": [
            {
                "label": "stage1_high_growth",
                "years": f"1-{n_high}",
                "growth_rate": g_high,
                "dividends": dividends,
            },
            {
                "label": "stage2_perpetuity",
                "years": f"{n_high + 1}-perpetuity",
                "growth_rate": g_stable,
                "first_dividend": d_n1_plus_1,
                "tv_nominal": tv_nominal,
                "pv_tv": pv_tv,
            },
        ],
    }


def _three_stage(
    d0: float,
    re: float,
    g_high: float,
    n_high: int,
    g_transition: float,
    n_transition: int,
    g_stable: float,
) -> dict[str, Any]:
    """Three-stage DDM: high-growth + transition + stable perpetuity.

    Transition phase: growth linearly fades from g_high to g_stable over n_transition years.
    """
    if re <= g_stable:
        raise ValueError(f"cost_of_equity ({re}) must be > g_stable ({g_stable}).")

    pv_stage1 = 0.0
    dividends_s1: list[float] = []
    d_t = d0

    # Stage 1
    for t in range(1, n_high + 1):
        d_t = d_t * (1.0 + g_high)
        dividends_s1.append(d_t)
        pv_stage1 += d_t / (1.0 + re) ** t

    # Stage 2: linear fade from g_high to g_stable over n_transition years
    pv_stage2 = 0.0
    dividends_s2: list[float] = []
    transition_growth_rates: list[float] = []
    t_offset = n_high
    for i in range(1, n_transition + 1):
        # Linear interpolation: starts at g_high + step, ends at g_stable
        frac = i / n_transition  # goes 1/n .. 1.0
        g_t = g_high + frac * (g_stable - g_high)
        if g_t >= re:
            raise ValueError(
                f"Transition growth rate at step {i} ({g_t:.4f}) >= Re ({re:.4f}). "
                "Reduce g_high or increase Re."
            )
        transition_growth_rates.append(g_t)
        d_t = d_t * (1.0 + g_t)
        dividends_s2.append(d_t)
        t_global = t_offset + i
        pv_stage2 += d_t / (1.0 + re) ** t_global

    # Stage 3: Gordon perpetuity
    n_total = n_high + n_transition
    d_terminal_plus_1 = d_t * (1.0 + g_stable)
    tv_nominal = d_terminal_plus_1 / (re - g_stable)
    pv_tv = tv_nominal / (1.0 + re) ** n_total

    price = pv_stage1 + pv_stage2 + pv_tv

    return {
        "price_per_share": price,
        "pv_breakdown": {
            "stage1_explicit": pv_stage1,
            "stage2_transition": pv_stage2,
            "stage3_terminal": pv_tv,
        },
        "stages": [
            {
                "label": "stage1_high_growth",
                "years": f"1-{n_high}",
                "growth_rate": g_high,
                "dividends": dividends_s1,
            },
            {
                "label": "stage2_transition",
                "years": f"{n_high + 1}-{n_total}",
                "growth_rates": transition_growth_rates,
                "dividends": dividends_s2,
            },
            {
                "label": "stage3_perpetuity",
                "years": f"{n_total + 1}-perpetuity",
                "growth_rate": g_stable,
                "first_dividend": d_terminal_plus_1,
                "tv_nominal": tv_nominal,
                "pv_tv": pv_tv,
            },
        ],
    }


def _h_model(
    d0: float,
    re: float,
    g_short: float,
    g_long: float,
    h: float,
) -> dict[str, Any]:
    """Fuller-Hsia H-model (1984).

    P0 = D0 * (1 + g_L) / (Re - g_L)  +  D0 * H * (g_S - g_L) / (Re - g_L)

    First term: stable-growth component.
    Second term: excess-growth component (the H premium).
    """
    if re <= g_long:
        raise ValueError(f"cost_of_equity ({re}) must be > g_long ({g_long}).")
    denom = re - g_long
    stable_component = d0 * (1.0 + g_long) / denom
    excess_component = d0 * h * (g_short - g_long) / denom
    price = stable_component + excess_component

    return {
        "price_per_share": price,
        "pv_breakdown": {
            "stable_component": stable_component,
            "excess_growth_component": excess_component,
        },
        "stages": [
            {
                "label": "h_model_stable",
                "growth_rate": g_long,
                "component": stable_component,
            },
            {
                "label": "h_model_excess",
                "g_short": g_short,
                "g_long": g_long,
                "h_half_life": h,
                "component": excess_component,
            },
        ],
    }


def _sustainability_check(
    d0: float,
    g: float,
    payout_ratio: float | None,
    roe: float | None,
) -> dict[str, Any]:
    """Check whether the growth assumption is supported by fundamentals.

    sustainable_growth = ROE * (1 - payout_ratio)
    gap = g_used - sustainable_growth (positive = growth exceeds fundamentals)
    """
    check: dict[str, Any] = {
        "growth_assumed": g,
        "payout_ratio": payout_ratio,
        "roe": roe,
    }

    warnings: list[str] = []

    if payout_ratio is not None and payout_ratio > 1.0:
        warnings.append(
            f"Payout ratio {payout_ratio:.2%} exceeds 100%; dividends exceed earnings. "
            "Growth assumption is not sustainable from retained earnings alone."
        )
        check["sustainable"] = False
        check["sustainable_growth"] = None
        check["warnings"] = warnings
        return check

    if roe is not None and roe < 0:
        warnings.append(
            "Negative ROE; sustainable growth formula is not meaningful. "
            "Recommend FCF-based valuation as primary."
        )
        check["sustainable"] = False
        check["sustainable_growth"] = None
        check["warnings"] = warnings
        return check

    if payout_ratio is not None and roe is not None:
        sustainable_growth = roe * (1.0 - payout_ratio)
        gap = g - sustainable_growth
        check["sustainable_growth"] = sustainable_growth
        check["gap"] = gap
        # Use a small tolerance to handle floating-point rounding on exact boundary
        if gap > 1e-10:
            check["sustainable"] = False
            warnings.append(
                f"Growth assumption {g:.2%} exceeds sustainable rate "
                f"{sustainable_growth:.2%} (ROE={roe:.2%}, payout={payout_ratio:.2%}). "
                "Gap of {:.2%} may require external financing or payout compression.".format(gap)
            )
        else:
            check["sustainable"] = True
    else:
        check["sustainable"] = None  # Cannot determine without both inputs
        check["sustainable_growth"] = None

    check["warnings"] = warnings
    return check


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    current_dividend_per_share: float,
    cost_of_equity: float,
    method: Literal["gordon", "two_stage", "three_stage", "h_model", "all"],
    gordon_growth: float = 0.025,
    stage1_growth: float | None = None,
    stage1_years: int | None = None,
    stage2_growth: float | None = None,
    stage2_years: int | None = None,
    terminal_growth: float = 0.025,
    h_half_life: float | None = None,
    h_short_growth: float | None = None,
    current_payout_ratio: float | None = None,
    current_roe: float | None = None,
    current_price: float | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Run one or more DDM variants.

    Args:
        current_dividend_per_share: Most recent declared annual dividend per share (D0).
        cost_of_equity: Required return on equity (Re). From cost_of_capital_builder.
        method: Which variant(s) to run. "all" runs every applicable model.
        gordon_growth: Constant growth rate for Gordon model.
        stage1_growth: High-growth phase rate (two_stage, three_stage, h_model).
        stage1_years: Number of high-growth years (two_stage, three_stage).
        stage2_growth: Transition-phase growth (three_stage only); used as linear fade target.
        stage2_years: Transition phase duration (three_stage).
        terminal_growth: Stable perpetuity growth (two_stage, three_stage).
        h_half_life: H value in H-model (half-life of growth decay in years).
        h_short_growth: Short-run growth for H-model (if None, uses stage1_growth).
        current_payout_ratio: For sustainability check.
        current_roe: For sustainability check.
        current_price: For implied upside/downside.
        data_as_of: ISO date of underlying data.
        source_provenance: Citation IDs.
    """
    if current_dividend_per_share <= 0:
        raise ValueError(
            "current_dividend_per_share must be positive. "
            "For non-dividend payers, use dcf_engine (FCFF) as primary valuation."
        )

    re = cost_of_equity
    d0 = current_dividend_per_share
    results: dict[str, Any] = {}
    warnings: list[str] = []

    run_gordon = method in ("gordon", "all")
    run_two = method in ("two_stage", "all")
    run_three = method in ("three_stage", "all")
    run_h = method in ("h_model", "all")

    # --- Gordon ---
    if run_gordon:
        results["gordon"] = _gordon(d0=d0, re=re, g=gordon_growth)

    # --- Two-stage ---
    if run_two:
        if stage1_growth is None:
            raise ValueError("stage1_growth is required for two_stage model.")
        if stage1_years is None:
            raise ValueError("stage1_years is required for two_stage model.")
        results["two_stage"] = _two_stage(
            d0=d0,
            re=re,
            g_high=stage1_growth,
            n_high=stage1_years,
            g_stable=terminal_growth,
        )

    # --- Three-stage ---
    if run_three:
        _three_missing: list[str] = []
        if stage1_growth is None:
            _three_missing.append("stage1_growth")
        if stage1_years is None:
            _three_missing.append("stage1_years")
        if stage2_years is None:
            _three_missing.append("stage2_years")
        if _three_missing and method == "three_stage":
            # Hard error when explicitly requested
            raise ValueError(f"Three-stage model requires: {', '.join(_three_missing)}.")
        elif not _three_missing:
            # stage2_growth is the mid-point of the transition fade; if not provided,
            # the linear fade goes directly from stage1_growth to terminal_growth
            _s2_g = (
                stage2_growth
                if stage2_growth is not None
                else (stage1_growth + terminal_growth) / 2
            )  # type: ignore[operator]
            results["three_stage"] = _three_stage(
                d0=d0,
                re=re,
                g_high=stage1_growth,  # type: ignore[arg-type]
                n_high=stage1_years,  # type: ignore[arg-type]
                g_transition=_s2_g,
                n_transition=stage2_years,  # type: ignore[arg-type]
                g_stable=terminal_growth,
            )
        # else: method == "all" and missing inputs — silently skip three_stage

    # --- H-model ---
    if run_h:
        if h_half_life is None:
            raise ValueError("h_half_life is required for h_model.")
        g_s = h_short_growth if h_short_growth is not None else stage1_growth
        if g_s is None:
            raise ValueError(
                "h_short_growth (or stage1_growth as fallback) is required for h_model."
            )
        results["h_model"] = _h_model(
            d0=d0,
            re=re,
            g_short=g_s,
            g_long=terminal_growth,
            h=h_half_life,
        )

    # Determine the primary result
    primary_key = (
        method if method != "all" else ("gordon" if "gordon" in results else next(iter(results)))
    )
    primary = results[primary_key]
    price_per_share = primary["price_per_share"]

    # Sustainability check — use stage1_growth if available, otherwise gordon_growth
    g_for_check = stage1_growth if stage1_growth is not None else gordon_growth
    sustainability = _sustainability_check(
        d0=d0,
        g=g_for_check,
        payout_ratio=current_payout_ratio,
        roe=current_roe,
    )
    warnings.extend(sustainability.get("warnings", []))

    # Upside computation
    implied_upside_pct: float | None = None
    if current_price is not None and current_price > 0:
        implied_upside_pct = (price_per_share - current_price) / current_price

    # Narrative
    narrative_parts: list[str] = [f"Method: {method}. Implied value ${price_per_share:.2f}/share."]
    if current_price is not None:
        direction = "upside" if (implied_upside_pct or 0) >= 0 else "downside"
        narrative_parts.append(
            f"Current price ${current_price:.2f}; "
            f"{abs((implied_upside_pct or 0) * 100):.1f}% {direction}."
        )
    if sustainability.get("sustainable") is False:
        narrative_parts.append(
            "Sustainability check flagged: dividend growth may exceed what fundamentals support."
        )

    # Build alternative_methods dict when method == "all"
    alternative_methods: dict[str, float] | None = None
    if method == "all" and len(results) > 1:
        alternative_methods = {k: v["price_per_share"] for k, v in results.items()}

    return {
        "method_used": method,
        "primary_model": primary_key,
        "current_dividend": d0,
        "cost_of_equity": re,
        "price_per_share": price_per_share,
        "pv_breakdown": primary["pv_breakdown"],
        "stages": primary["stages"],
        "sustainability": sustainability,
        "alternative_methods": alternative_methods,
        "current_price": current_price,
        "implied_upside_pct": implied_upside_pct,
        "narrative": " ".join(narrative_parts),
        "warnings": warnings,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="ddm_family",
        category=Category.ALTERNATIVE_VALUATION,
        one_liner=(
            "DDM family: Gordon, two-stage, three-stage, H-model; "
            "dividend sustainability check included."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Value dividend-paying equities directly from their dividend stream. "
            "Provides four DDM variants (Gordon, two-stage, three-stage, H-model) "
            "with an integrated sustainability check against ROE and payout ratio."
        ),
        when_to_use=[
            "Utilities, mature financials, mature REITs where dividends are the primary"
            " return mechanism.",
            "As a cross-check alongside DCF for any dividend-paying name.",
            "When dividend policy is stable and management guides on dividend growth.",
            "Post-dividend-policy-change update reports to quantify the value impact.",
        ],
        when_not_to_use=[
            "Non-dividend payers — use dcf_engine (FCFF) as primary.",
            "REITs as primary valuation — use reit_valuation_panel (AFFO/NAV);"
            " DDM is a cross-check only.",
            "High-growth names where reinvestment dominates — DDM understates value"
            " when payout is very low.",
            "Companies with negative ROE or payout > 100% — sustainability check"
            " will flag; prefer dcf_engine.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "current_dividend_per_share": HelperParam(
                type="float",
                description=(
                    "Most recent declared annual dividend per share (D0). Must be positive."
                ),
                required=True,
            ),
            "cost_of_equity": HelperParam(
                type="float",
                description="Required return on equity (Re). From cost_of_capital_builder.",
                required=True,
            ),
            "method": HelperParam(
                type="str",
                description="gordon | two_stage | three_stage | h_model | all.",
                required=True,
            ),
            "gordon_growth": HelperParam(
                type="float",
                default=0.025,
                description="Constant growth rate for Gordon model. Must be < Re.",
                required=False,
            ),
            "stage1_growth": HelperParam(
                type="float",
                default=None,
                description="High-growth phase rate. Required for two_stage, three_stage, h_model.",
                required=False,
            ),
            "stage1_years": HelperParam(
                type="int",
                default=None,
                description="High-growth phase duration. Required for two_stage, three_stage.",
                required=False,
            ),
            "stage2_growth": HelperParam(
                type="float",
                default=None,
                description=(
                    "Transition phase midpoint growth (three_stage). Defaults to"
                    " midpoint of stage1_growth and terminal_growth."
                ),
                required=False,
            ),
            "stage2_years": HelperParam(
                type="int",
                default=None,
                description="Transition phase duration (three_stage). Required for three_stage.",
                required=False,
            ),
            "terminal_growth": HelperParam(
                type="float",
                default=0.025,
                description=(
                    "Stable perpetuity growth rate. Must be < Re."
                    " Used by two_stage, three_stage, h_model."
                ),
                required=False,
            ),
            "h_half_life": HelperParam(
                type="float",
                default=None,
                description="H value: half-life of growth decay in years. Required for h_model.",
                required=False,
            ),
            "h_short_growth": HelperParam(
                type="float",
                default=None,
                description=(
                    "Short-run growth for h_model. Defaults to stage1_growth if not provided."
                ),
                required=False,
            ),
            "current_payout_ratio": HelperParam(
                type="float",
                default=None,
                description="Current dividend payout ratio. Used for sustainability check.",
                required=False,
            ),
            "current_roe": HelperParam(
                type="float",
                default=None,
                description="Current return on equity. Used for sustainability check.",
                required=False,
            ),
            "current_price": HelperParam(
                type="float",
                default=None,
                description="Current market price for upside/downside computation.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="ddm_output",
                type="structured_object",
                description=(
                    "DDM valuation: price_per_share, pv_breakdown by stage, "
                    "sustainability check (sustainable, gap, warnings), "
                    "alternative_methods (when method=all), implied_upside_pct."
                ),
            ),
        ],
        produces_artifacts=["ddm_output"],
        consumes_artifacts=["cost_of_capital_output"],
        data_dependencies=["eodhd.dividends", "cost_of_capital_builder"],
    ),
    skill_doc=SkillDocRef(
        path="skills/ddm_family.md",
        estimated_tokens=1800,
    ),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
