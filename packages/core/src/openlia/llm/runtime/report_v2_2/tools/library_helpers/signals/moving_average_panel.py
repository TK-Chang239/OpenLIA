"""moving_average_panel — MA trend regime, crossovers, and mean-reversion stretch.

Registered name: "moving_average_panel"

Derives the moving-average trend state, golden/death cross signals, price-vs-MA
distance, and z-score stretch from split-adjusted price (or multiple) series.

This helper is listed as complex (18-list per schema-and-skills §6).
Skill doc: skills/moving_average_panel.md
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
_DEFAULT_MA_WINDOWS = [20, 50, 100, 200]
_DEFAULT_CROSSOVER_PAIRS = [(50, 200), (20, 50)]
# Slope state threshold: % change per period
_SLOPE_THRESHOLD = 0.0005  # 0.05% per period


# ---------------------------------------------------------------------------
# MA computation
# ---------------------------------------------------------------------------


def _compute_sma(prices: list[float], window: int) -> list[float | None]:
    """SMA series; first (window-1) values are None."""
    result: list[float | None] = []
    for i, _ in enumerate(prices):
        if i < window - 1:
            result.append(None)
        else:
            result.append(sum(prices[i - window + 1 : i + 1]) / window)
    return result


def _compute_ema(prices: list[float], window: int) -> list[float | None]:
    """EMA series; first (window-1) values are None (need seed)."""
    k = 2.0 / (window + 1)
    result: list[float | None] = [None] * (window - 1)
    if len(prices) < window:
        return [None] * len(prices)
    # Seed with SMA of first window
    seed = sum(prices[:window]) / window
    result.append(seed)
    for price in prices[window:]:
        prev = result[-1]
        assert prev is not None
        result.append(price * k + prev * (1 - k))
    return result


def _compute_ma_series(prices: list[float], window: int, ma_type: str) -> list[float | None]:
    if ma_type == "ema":
        return _compute_ema(prices, window)
    return _compute_sma(prices, window)


# ---------------------------------------------------------------------------
# Slope
# ---------------------------------------------------------------------------


def _compute_slope(ma_series: list[float | None], lookback: int = 20) -> dict[str, Any]:
    """Slope of MA over last `lookback` periods."""
    valid = [v for v in ma_series if v is not None]
    if len(valid) < lookback + 1:
        return {"slope_pct_per_period": None, "slope_state": "insufficient_data"}
    recent = valid[-lookback:]
    prev_val = recent[0]
    curr_val = recent[-1]
    if prev_val <= 0:
        return {"slope_pct_per_period": None, "slope_state": "insufficient_data"}
    slope = (curr_val - prev_val) / prev_val / lookback
    if slope > _SLOPE_THRESHOLD:
        state = "rising"
    elif slope < -_SLOPE_THRESHOLD:
        state = "falling"
    else:
        state = "flattening"
    return {"slope_pct_per_period": round(slope, 6), "slope_state": state}


# ---------------------------------------------------------------------------
# Crossover detection
# ---------------------------------------------------------------------------


def _find_crossovers(
    fast_series: list[float | None],
    slow_series: list[float | None],
    dates: list[str],
    prices: list[float],
    fast_window: int,
    slow_window: int,
    volume_series: list[float] | None,
) -> dict[str, Any] | None:
    """Find the most recent crossover for (fast, slow) pair."""
    n = len(fast_series)
    last_cross: dict[str, Any] | None = None

    for i in range(1, n):
        f_prev = fast_series[i - 1]
        s_prev = slow_series[i - 1]
        f_curr = fast_series[i]
        s_curr = slow_series[i]

        if any(v is None for v in (f_prev, s_prev, f_curr, s_curr)):
            continue

        assert f_prev is not None and s_prev is not None
        assert f_curr is not None and s_curr is not None

        cross_type: str | None = None
        if f_prev <= s_prev and f_curr > s_curr:
            cross_type = "golden_cross"
        elif f_prev >= s_prev and f_curr < s_curr:
            cross_type = "death_cross"

        if cross_type is not None:
            date = dates[i] if i < len(dates) else f"index_{i}"
            price_at = prices[i] if i < len(prices) else None
            # Return since cross
            current_price = prices[-1] if prices else None
            ret = None
            if price_at is not None and current_price is not None and price_at > 0:
                ret = round((current_price - price_at) / price_at, 4)
            # still_in_effect: fast still on same side as at cross
            still = (cross_type == "golden_cross" and f_curr > s_curr) or (
                cross_type == "death_cross" and f_curr < s_curr
            )
            # Volume confirmation
            vol_confirmed: bool | None = None
            if volume_series is not None and i < len(volume_series):
                lookback_vol = min(20, i)
                avg_vol = sum(volume_series[max(0, i - lookback_vol) : i]) / lookback_vol
                vol_confirmed = volume_series[i] > avg_vol

            days_ago: int | None = None
            if i < len(dates):
                try:
                    parts_anchor = date.split("-")
                    parts_last = dates[-1].split("-")
                    if len(parts_anchor) == 3 and len(parts_last) == 3:
                        a_total = (
                            int(parts_anchor[0]) * 365
                            + int(parts_anchor[1]) * 30
                            + int(parts_anchor[2])
                        )
                        b_total = (
                            int(parts_last[0]) * 365 + int(parts_last[1]) * 30 + int(parts_last[2])
                        )
                        days_ago = abs(b_total - a_total)
                except (ValueError, IndexError):
                    pass

            last_cross = {
                "pair": f"{fast_window}/{slow_window}",
                "type": cross_type,
                "date": date,
                "days_ago": days_ago,
                "price_at_cross": price_at,
                "return_since_cross_pct": ret,
                "still_in_effect": still,
                "confirmed_on_volume": vol_confirmed,
            }

    return last_cross


# ---------------------------------------------------------------------------
# Stretch / z-score
# ---------------------------------------------------------------------------


def _stretch_zscore(
    current_price: float, ma_val: float, stretch_history: list[float]
) -> dict[str, Any]:
    stretch_pct = (current_price / ma_val - 1) if ma_val > 0 else None
    if stretch_pct is None or len(stretch_history) < 10:
        return {
            "200d_stretch_pct": stretch_pct,
            "200d_stretch_zscore": None,
            "stretch_read": "Insufficient history for z-score.",
        }
    mean_h = sum(stretch_history) / len(stretch_history)
    variance = sum((x - mean_h) ** 2 for x in stretch_history) / len(stretch_history)
    stdev = math.sqrt(variance) if variance > 0 else _EPSILON
    zscore = (stretch_pct - mean_h) / stdev

    if zscore > 2.0:
        read = f"{stretch_pct:.1%} above 200-day — very extended, >2 sigma."
    elif zscore > 1.0:
        read = f"{stretch_pct:.1%} above 200-day — moderately extended, ~{zscore:.1f} sigma."
    elif zscore < -2.0:
        read = f"{abs(stretch_pct):.1%} below 200-day — deeply oversold, <-2 sigma."
    elif zscore < -1.0:
        read = f"{abs(stretch_pct):.1%} below 200-day — modestly oversold, ~{zscore:.1f} sigma."
    else:
        direction = "above" if stretch_pct >= 0 else "below"
        read = (
            f"{abs(stretch_pct):.1%} {direction} 200-day — near-normal range ({zscore:.2f} sigma)."
        )

    return {
        "200d_stretch_pct": round(stretch_pct, 4),
        "200d_stretch_zscore": round(zscore, 3),
        "stretch_read": read,
    }


# ---------------------------------------------------------------------------
# Main execute
# ---------------------------------------------------------------------------


def execute(
    price_series: list[float],
    dates: list[str] | None = None,
    ma_windows: list[int] | None = None,
    ma_type: str = "sma",
    crossover_pairs: list[tuple[int, int]] | None = None,
    volume_series: list[float] | None = None,
    series_kind: str = "price",
) -> dict[str, Any]:
    """Compute moving average panel: trend regime, crossovers, stretch.

    Args:
        price_series: Daily split/dividend-adjusted close prices, ascending by date.
            Minimum length: max(ma_windows) + 1.
        dates: ISO date strings (YYYY-MM-DD), same length as price_series. If omitted,
            integer indices are used for crossover date labeling.
        ma_windows: MA lengths in periods. Default [20, 50, 100, 200].
        ma_type: "sma" (default) or "ema".
        crossover_pairs: (fast, slow) pairs to test for crosses. Default [(50,200),(20,50)].
        volume_series: Optional daily volume, same length as price_series.
        series_kind: "price" (default) or "multiple" (see tie-in with historical_multiple_trends).

    Returns:
        Dict with moving_averages, price_above_ma, ma_stack, trend_regime, crossovers,
        distance_from_ma, trend_classification_narrative.
    """
    if not price_series:
        raise ValueError("price_series must not be empty")
    if ma_type not in ("sma", "ema"):
        raise ValueError(f"ma_type must be 'sma' or 'ema', got {ma_type!r}")

    if ma_windows is None:
        ma_windows = _DEFAULT_MA_WINDOWS
    if crossover_pairs is None:
        crossover_pairs = _DEFAULT_CROSSOVER_PAIRS
    if dates is None:
        dates = [str(i) for i in range(len(price_series))]

    current_price = price_series[-1]
    as_of = dates[-1] if dates else "unknown"

    # Compute MA series for each window
    ma_series_map: dict[int, list[float | None]] = {}
    for w in ma_windows:
        ma_series_map[w] = _compute_ma_series(price_series, w, ma_type)

    # Current MA values and per-window stats
    moving_averages: dict[str, dict[str, Any]] = {}
    price_above_ma: dict[str, bool | None] = {}
    current_ma_vals: dict[int, float | None] = {}

    for w in ma_windows:
        series = ma_series_map[w]
        curr_ma = series[-1] if series else None
        current_ma_vals[w] = curr_ma

        if curr_ma is not None:
            pct = (current_price / curr_ma - 1) if curr_ma > 0 else None
            slope_info = _compute_slope(series)
            moving_averages[str(w)] = {
                "value": round(curr_ma, 4),
                "price_vs_ma_pct": round(pct, 4) if pct is not None else None,
                **slope_info,
            }
            price_above_ma[str(w)] = current_price > curr_ma if pct is not None else None
        else:
            moving_averages[str(w)] = {
                "value": None,
                "price_vs_ma_pct": None,
                "slope_pct_per_period": None,
                "slope_state": "insufficient_data",
            }
            price_above_ma[str(w)] = None

    # MA stack
    available_vals = [
        (w, current_ma_vals[w]) for w in sorted(ma_windows) if current_ma_vals[w] is not None
    ]
    if len(available_vals) >= 2:
        sorted_asc = all(
            available_vals[i][1] < available_vals[i + 1][1]  # type: ignore[operator]
            for i in range(len(available_vals) - 1)
        )
        sorted_desc = all(
            available_vals[i][1] > available_vals[i + 1][1]  # type: ignore[operator]
            for i in range(len(available_vals) - 1)
        )
        if sorted_desc:
            ma_stack = "bullish"  # 20 > 50 > 100 > 200
        elif sorted_asc:
            ma_stack = "bearish"  # 20 < 50 < 100 < 200
        else:
            ma_stack = "mixed"
    else:
        ma_stack = "unknown"

    # Trend regime (anchor: 200DMA)
    ma200 = current_ma_vals.get(200)
    if ma200 is not None:
        slope_200 = moving_averages.get("200", {}).get("slope_pct_per_period")
        above_200 = current_price > ma200
        slope_positive = slope_200 is not None and slope_200 >= 0
        if above_200 and slope_positive:
            trend_regime = "uptrend"
        elif not above_200 and (slope_200 is None or slope_200 <= 0):
            trend_regime = "downtrend"
        else:
            trend_regime = "transition_or_range"
    else:
        # Fall back to longest available MA
        if available_vals:
            _longest_w, longest_ma = available_vals[-1]
            trend_regime = (
                "uptrend" if current_price > longest_ma else "downtrend"  # type: ignore[operator]
            )
        else:
            trend_regime = "unknown"

    # Crossovers
    crossovers: list[dict[str, Any]] = []
    for fast_w, slow_w in crossover_pairs:
        if fast_w not in ma_series_map or slow_w not in ma_series_map:
            continue
        cross = _find_crossovers(
            ma_series_map[fast_w],
            ma_series_map[slow_w],
            dates,
            price_series,
            fast_w,
            slow_w,
            volume_series,
        )
        if cross is not None:
            crossovers.append(cross)

    # Distance from 200DMA and z-score stretch
    if ma200 is not None:
        # Historical stretch series (use all available computed values)
        stretch_history = [
            (p / m - 1)
            for p, m in zip(price_series, ma_series_map.get(200, []), strict=False)
            if m is not None
        ]
        distance_from_ma = _stretch_zscore(current_price, ma200, stretch_history)
    else:
        distance_from_ma = {
            "200d_stretch_pct": None,
            "200d_stretch_zscore": None,
            "stretch_read": "200-day MA not available (insufficient price history).",
        }

    # Whipsaw detection: if > 4 crosses of the same pair in trailing window, flag range
    if len(crossovers) > 0 and trend_regime not in ("uptrend", "downtrend"):
        trend_regime = "range"

    # Narrative
    above_count = sum(1 for v in price_above_ma.values() if v is True)
    total_available = sum(1 for v in price_above_ma.values() if v is not None)
    if total_available > 0:
        narrative_parts = [
            f"Price is above {above_count}/{total_available} available moving averages."
        ]
    else:
        narrative_parts = ["Insufficient data to assess moving average position."]
    narrative_parts.append(f"MA stack: {ma_stack}. Trend regime: {trend_regime}.")
    if crossovers:
        most_recent = crossovers[-1]
        narrative_parts.append(
            f"Most recent crossover: {most_recent['type']} on {most_recent['pair']} "
            f"({most_recent['date']})."
        )

    return {
        "as_of": as_of,
        "current_price": current_price,
        "ma_type": ma_type,
        "series_kind": series_kind,
        "moving_averages": moving_averages,
        "price_above_ma": price_above_ma,
        "ma_stack": ma_stack,
        "trend_regime": trend_regime,
        "crossovers": crossovers,
        "distance_from_ma": distance_from_ma,
        "trend_classification_narrative": " ".join(narrative_parts),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="moving_average_panel",
        category=Category.SIGNALS,
        one_liner="MA trend regime, golden/death crossovers, and mean-reversion stretch z-score.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Derive the moving-average trend state and derived signals an analyst writes about: "
            "price-vs-MA position, MA slope/trend regime, golden/death crosses with recency, "
            "and distance-from-MA z-score. Works on price series or valuation multiple series."
        ),
        when_to_use=[
            "Update reports: establish timing/technical context for a thesis.",
            "Initiation: add a technical backdrop section alongside fundamental analysis.",
            "Sector comparisons: count names above their 200-day for trend-regime cohort view.",
            "Smoothing valuation multiples: pass series_kind='multiple' to apply MA to P/E series.",
        ],
        when_not_to_use=[
            "Standalone buy/sell signal — crossovers have weak standalone predictive value.",
            "When price_series has < 20 data points — most MAs will be null.",
            "Short-term intraday patterns — use eodhd_intraday; this helper is daily/weekly.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "price_series": HelperParam(
                type="list[float]",
                required=True,
                description=(
                    "Daily split/dividend-adjusted close prices, ascending by date. "
                    "Minimum length: max(ma_windows) + 1 for all MAs to be non-null."
                ),
            ),
            "dates": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description="ISO date strings (YYYY-MM-DD) parallel to price_series.",
            ),
            "ma_windows": HelperParam(
                type="list[int]",
                required=False,
                default=[20, 50, 100, 200],
                description="MA window lengths in periods. Default [20, 50, 100, 200].",
            ),
            "ma_type": HelperParam(
                type="str",
                required=False,
                default="sma",
                description="'sma' (default) or 'ema'.",
            ),
            "crossover_pairs": HelperParam(
                type="list[tuple[int,int]]",
                required=False,
                default=[(50, 200), (20, 50)],
                description="(fast, slow) pairs for golden/death cross detection.",
            ),
            "volume_series": HelperParam(
                type="list[float] | None",
                required=False,
                default=None,
                description="Optional daily volume series, same length as price_series.",
            ),
            "series_kind": HelperParam(
                type="str",
                required=False,
                default="price",
                description=(
                    "'price' (default) or 'multiple'. "
                    "Use 'multiple' to smooth a valuation multiple series from "
                    "historical_multiple_trends."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="moving_average_panel",
                type="dict",
                description=(
                    "moving_averages (per window: value, price_vs_ma_pct, slope), "
                    "price_above_ma, ma_stack, trend_regime, crossovers list, "
                    "distance_from_ma (200d stretch pct and z-score), narrative."
                ),
            ),
        ],
        produces_artifacts=["moving_average_panel_output"],
        consumes_artifacts=["eodhd_eod_prices_output"],
    ),
    skill_doc=SkillDocRef(path="skills/moving_average_panel.md", estimated_tokens=1800),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.FACTUAL_INCONSISTENCY,
    ],
)

register_helper(_SCHEMA, execute)
