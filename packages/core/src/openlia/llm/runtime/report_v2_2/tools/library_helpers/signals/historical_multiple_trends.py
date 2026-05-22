"""historical_multiple_trends — Historical P/E, EV/EBITDA, P/B, P/S vs own history.

Registered name: "historical_multiple_trends"

Places the current valuation multiple in the context of the company's own history
(and optionally its sector), to distinguish genuine cheapness from a deserved de-rating.

This helper is listed as complex (18-list per schema-and-skills §6).
Skill doc: skills/historical_multiple_trends.md
"""

from __future__ import annotations

import math
from typing import Any

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

_EPSILON = 1e-9
_DEFAULT_MULTIPLES = ["pe_ttm", "ps_ttm", "ev_ebitda", "pb"]
_DEFAULT_WINDOWS_YEARS = [1, 3, 5, 10]


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[float], p: float) -> float:
    """Interpolated percentile from sorted list. p in [0, 1]."""
    if not sorted_values:
        raise ValueError("sorted_values must not be empty")
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    idx = p * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _descriptive_stats(values: list[float]) -> dict[str, float]:
    if not values:
        raise ValueError("values must not be empty")
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    stdev = math.sqrt(variance) if variance > 0 else 0.0
    sv = sorted(values)
    return {
        "count": float(n),
        "min": sv[0],
        "p25": _percentile(sv, 0.25),
        "median": _percentile(sv, 0.50),
        "mean": round(mean, 4),
        "p75": _percentile(sv, 0.75),
        "max": sv[-1],
        "stdev": round(stdev, 4),
    }


def _percentile_rank(values: list[float], current: float) -> float:
    """Fraction of historical values strictly below current."""
    if not values:
        return 0.0
    return sum(1 for v in values if v < current) / len(values)


def _z_score(current: float, mean: float, stdev: float) -> float | None:
    if stdev <= 0:
        return None
    return round((current - mean) / stdev, 4)


def _ols_slope(values: list[float]) -> float:
    """Simple OLS slope of values over index (trend direction)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / max(den, _EPSILON)


def _rerating_read(slope: float, values: list[float]) -> str:
    """Qualitative re-rating trend description."""
    if not values:
        return "insufficient data"
    if slope > 0.05:
        return f"re-rating: multiple expanding from ~{values[0]:.1f}x to ~{values[-1]:.1f}x"
    if slope < -0.05:
        return f"de-rating: multiple contracting from ~{values[0]:.1f}x to ~{values[-1]:.1f}x"
    return f"flat / mean-reverting: range {min(values):.1f}x-{max(values):.1f}x"


# ---------------------------------------------------------------------------
# Per-multiple analysis
# ---------------------------------------------------------------------------


def _analyze_multiple(
    multiple_name: str,
    current_value: float,
    history_series: list[float],
    windows_years: list[int],
    sector_median_series: list[float] | None,
) -> dict[str, Any]:
    """Compute statistics, z-scores, percentile, and re-rating trend for one multiple."""
    # Filter NaN / non-positive P/E (loss periods)
    nm_count = sum(
        1 for v in history_series if v is None or (multiple_name in ("pe_ttm", "pb") and v <= 0)
    )

    clean_history = [
        v
        for v in history_series
        if v is not None and not (math.isnan(v) if isinstance(v, float) else False)
    ]
    # For PE specifically, exclude <= 0 (NM periods)
    if multiple_name in ("pe_ttm",):
        clean_history = [v for v in clean_history if v > 0]

    if not clean_history:
        return {
            "current": current_value,
            "history": {},
            "z_score_by_window": {},
            "percentile_rank_by_window": {},
            "vs_median_pct_by_window": {},
            "rerating_trend": "insufficient data",
            "valuation_read": "No valid history available.",
            "nm_periods": nm_count,
            "warnings": ["No valid historical data for this multiple."],
        }

    history_by_window: dict[str, dict[str, float]] = {}
    z_scores: dict[str, float | None] = {}
    percentile_ranks: dict[str, float] = {}
    vs_median_pct: dict[str, float | None] = {}

    for years in windows_years:
        key = f"{years}y"
        # Use last N * 252 observations as a rough proxy (daily) or N values if quarterly
        # We treat history_series as already filtered to the relevant window
        # For simplicity, take the last min(years*4, len) observations
        # (caller should slice to the intended history)
        n_obs = min(years * 4, len(clean_history))  # quarterly cadence default
        window_vals = clean_history[-n_obs:] if n_obs > 0 else clean_history

        if not window_vals:
            continue

        stats = _descriptive_stats(window_vals)
        history_by_window[key] = {k: round(v, 4) for k, v in stats.items()}

        mean_w = stats["mean"]
        stdev_w = stats["stdev"]
        median_w = stats["median"]

        z_scores[key] = _z_score(current_value, mean_w, stdev_w)
        percentile_ranks[key] = round(_percentile_rank(window_vals, current_value), 4)
        vs_median_pct[key] = (
            round((current_value - median_w) / abs(median_w), 4)
            if abs(median_w) > _EPSILON
            else None
        )

    # Re-rating trend using longest available window
    longest_n = min(max(windows_years) * 4, len(clean_history))
    trend_vals = clean_history[-longest_n:]
    slope = _ols_slope(trend_vals)
    rerating_trend = _rerating_read(slope, trend_vals)

    # Valuation read (use longest window for primary framing)
    longest_key = f"{max(windows_years)}y"
    max_yrs = max(windows_years)
    if longest_key in percentile_ranks:
        pct = percentile_ranks[longest_key]
        pct_int = int(pct * 100)
        if pct_int <= 10:
            read = (
                f"{pct_int}th percentile of {max_yrs}y history"
                " — near historical lows; verify no structural impairment."
            )
        elif pct_int >= 90:
            read = (
                f"{pct_int}th percentile of {max_yrs}y history"
                " — near historical highs; premium must be earned."
            )
        elif pct_int < 30:
            read = f"{pct_int}th percentile of {max_yrs}y history — modestly cheap vs own history."
        elif pct_int > 70:
            read = (
                f"{pct_int}th percentile of {max_yrs}y history — modestly expensive vs own history."
            )
        else:
            read = f"{pct_int}th percentile of {max_yrs}y history — mid-range vs own history."
    else:
        read = "Insufficient history for percentile read."

    warnings: list[str] = []
    if nm_count > 0:
        warnings.append(
            f"{nm_count} NM (not meaningful) periods excluded from {multiple_name} stats."
        )
    for key, pct_val in percentile_ranks.items():
        if pct_val <= 0.10:
            pct_label = int(pct_val * 100)
            warnings.append(
                f"{multiple_name} at {pct_label}th percentile ({key})"
                " — near historical low; check for structural de-rating."
            )
        elif pct_val >= 0.90:
            pct_label = int(pct_val * 100)
            warnings.append(
                f"{multiple_name} at {pct_label}th percentile ({key})"
                " — near historical high; assess premium sustainability."
            )

    # Sector relative (if provided)
    sector_result: dict[str, Any] | None = None
    if sector_median_series:
        clean_sector = [v for v in sector_median_series if v is not None and v > 0]
        if clean_sector:
            current_sector_median = clean_sector[-1]
            hist_premiums = []
            for comp_val, sec_val in zip(clean_history, clean_sector, strict=False):
                if sec_val > 0:
                    hist_premiums.append((comp_val - sec_val) / sec_val)
            current_premium = (
                (current_value - current_sector_median) / current_sector_median
                if current_sector_median > 0
                else None
            )
            avg_premium = sum(hist_premiums) / len(hist_premiums) if hist_premiums else None
            sector_result = {
                "current_sector_median": round(current_sector_median, 4),
                "current_premium_to_sector_pct": round(current_premium, 4)
                if current_premium is not None
                else None,
                "historical_avg_premium_pct": round(avg_premium, 4)
                if avg_premium is not None
                else None,
            }

    result: dict[str, Any] = {
        "current": current_value,
        "history": history_by_window,
        "z_score_by_window": {k: v for k, v in z_scores.items()},
        "percentile_rank_by_window": percentile_ranks,
        "vs_median_pct_by_window": {k: v for k, v in vs_median_pct.items()},
        "rerating_trend": rerating_trend,
        "valuation_read": read,
        "nm_periods": nm_count,
        "warnings": warnings,
    }
    if sector_result is not None:
        result["relative_to_sector"] = sector_result

    return result


# ---------------------------------------------------------------------------
# Main execute
# ---------------------------------------------------------------------------


def execute(
    multiples_data: dict[str, dict[str, Any]],
    windows_years: list[int] | None = None,
    sector_median_series: dict[str, list[float]] | None = None,
    forward_estimates: dict[str, float] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Compute historical multiple trends and percentile positioning.

    Args:
        multiples_data: Dict mapping multiple name to {"current": float, "history": list[float]}.
            Multiple names: "pe_ttm", "ps_ttm", "ev_ebitda", "pb" (or custom).
            history is ordered oldest-first. NM periods should be None or 0.
        windows_years: Year windows for stats. Default [1, 3, 5, 10].
        sector_median_series: Optional dict mapping multiple name to sector median history series,
            parallel to multiples_data[name]["history"].
        forward_estimates: Optional dict with forward multiple values, e.g.
            {"pe_forward": 15.8}. Used to compute implied EPS growth.
        as_of: Reference date string for output labeling.

    Returns:
        Dict with per-multiple analysis, forward_vs_trailing (if provided),
        mean_reversion_caveat, data_as_of.
    """
    if not multiples_data:
        raise ValueError("multiples_data must not be empty")

    if windows_years is None:
        windows_years = _DEFAULT_WINDOWS_YEARS

    results: dict[str, Any] = {}
    nm_periods_flagged: list[str] = []

    for mult_name, mult_info in multiples_data.items():
        current_val = float(mult_info.get("current") or 0)
        history_raw = mult_info.get("history") or []
        history_clean: list[float] = [float(v) for v in history_raw if v is not None]

        sector_s: list[float] | None = None
        if sector_median_series and mult_name in sector_median_series:
            sector_s = [float(v) for v in sector_median_series[mult_name] if v is not None]

        analysis = _analyze_multiple(
            mult_name,
            current_val,
            history_clean,
            windows_years,
            sector_s,
        )

        results[mult_name] = analysis

        if analysis["nm_periods"] > 0:
            nm_periods_flagged.append(
                f"{mult_name}: {analysis['nm_periods']} NM period(s) excluded."
            )

    # Forward/trailing spread
    # forward_estimates keys: e.g. "pe_ttm_forward" or "pe_forward" or "pe_ttm".
    # Strategy: strip "_forward" suffix; also try replacing "_forward" with "_ttm".
    forward_section: dict[str, Any] | None = None
    if forward_estimates:
        for fwd_key, fwd_val in forward_estimates.items():
            if not fwd_val or float(fwd_val) <= 0:
                continue
            # Derive the matching trailing key
            # e.g. "pe_ttm_forward" -> try "pe_ttm" first, then "pe"
            # e.g. "pe_forward" -> try "pe_ttm" first, then "pe"
            base = fwd_key.replace("_forward", "").replace("forward_", "").rstrip("_")
            candidates = [base, base + "_ttm"]
            ttm_key: str | None = None
            for cand in candidates:
                if cand in multiples_data:
                    ttm_key = cand
                    break
            if ttm_key is None:
                # Try any key that starts with base
                for k in multiples_data:
                    if k.startswith(base):
                        ttm_key = k
                        break
            if ttm_key is None:
                continue
            ttm_val = multiples_data[ttm_key].get("current")
            if ttm_val is None:
                continue
            ttm_float = float(ttm_val)
            fwd_float = float(fwd_val)
            implied_growth = ttm_float / fwd_float - 1 if fwd_float > 0 else None
            forward_section = {
                "multiple": base,
                "forward_value": fwd_float,
                "trailing_value": ttm_float,
                "implied_growth": round(implied_growth, 4) if implied_growth is not None else None,
                "read": (
                    f"Forward multiple {fwd_float:.1f}x vs trailing {ttm_float:.1f}x "
                    f"implies ~{implied_growth:.1%} growth in the denominator."
                    if implied_growth is not None
                    else "Cannot compute implied growth."
                ),
            }
            break  # first valid pair

    output: dict[str, Any] = {**results}
    if nm_periods_flagged:
        output["nm_periods_flagged"] = nm_periods_flagged
    if forward_section:
        output["forward_vs_trailing"] = forward_section
    output["mean_reversion_caveat"] = (
        "A low z-score or percentile is only an opportunity if the business has not "
        "structurally changed. Pair with margin_trajectory_regression and roic_panel "
        "before interpreting a discount as cheap."
    )
    output["data_as_of"] = as_of or "unknown"

    return output


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="historical_multiple_trends",
        category=Category.SIGNALS,
        one_liner="Historical P/E, EV/EBITDA, P/B, P/S vs own history: percentile, z-score, trend.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Place current valuation multiples in the context of the company's own history "
            "(5Y/10Y) and optionally vs sector median. Computes percentile rank, z-score, "
            "re-rating/de-rating OLS trend, and forward/trailing spread from estimates."
        ),
        when_to_use=[
            "Initiation: frame whether current multiple is cheap/expensive vs own history.",
            "Update: quantify how much the multiple has shifted post-earnings.",
            "Sector: cross-company premium/discount mapping vs sector median trajectory.",
        ],
        when_not_to_use=[
            "Companies with <2 years of public history — insufficient data for trend.",
            "Loss-making periods where P/E is NM — use P/S or EV/Sales instead.",
            "Real-time valuation — this is a historical context tool, not a live screener.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "multiples_data": HelperParam(
                type="dict[str, dict]",
                required=True,
                description=(
                    'Dict mapping multiple name to {"current": float, "history": list[float]}. '
                    "Names: pe_ttm, ps_ttm, ev_ebitda, pb. "
                    "history is ordered oldest-first; use None for NM (loss) periods."
                ),
            ),
            "windows_years": HelperParam(
                type="list[int]",
                required=False,
                default=[1, 3, 5, 10],
                description="Year windows for descriptive stats. Default [1, 3, 5, 10].",
            ),
            "sector_median_series": HelperParam(
                type="dict[str, list[float]] | None",
                required=False,
                default=None,
                description=(
                    "Sector peer median multiple history series, parallel to history in "
                    "multiples_data. Enables premium/discount vs sector overlay."
                ),
            ),
            "forward_estimates": HelperParam(
                type="dict[str, float] | None",
                required=False,
                default=None,
                description=(
                    'Forward multiple values, e.g. {"pe_forward": 15.8}. '
                    "Used to compute forward/trailing spread and implied growth."
                ),
            ),
            "as_of": HelperParam(
                type="str | None",
                required=False,
                default=None,
                description="Reference date YYYY-MM-DD for output labeling.",
            ),
        },
        outputs=[
            HelperOutput(
                name="historical_multiple_trends",
                type="dict",
                description=(
                    "Per multiple: current, history stats by window, z_score_by_window, "
                    "percentile_rank_by_window, rerating_trend, valuation_read, warnings. "
                    "Optional: forward_vs_trailing, nm_periods_flagged, mean_reversion_caveat."
                ),
            ),
        ],
        produces_artifacts=["historical_multiple_trends_output"],
        consumes_artifacts=["eodhd_market_cap_history_output"],
    ),
    skill_doc=SkillDocRef(path="skills/historical_multiple_trends.md", estimated_tokens=1900),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.FACTUAL_INCONSISTENCY,
    ],
)

register_helper(_SCHEMA, execute)
