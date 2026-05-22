"""drawdown_panel — per-window max drawdown, duration, recovery, Calmar, and Sortino.

Registered name: "drawdown_panel"

Per design §5.1:
  - Max drawdown over 1Y / 3Y / 5Y / 10Y / since-IPO windows
  - Peak-to-trough duration and trough-to-recovery duration
  - Underwater curve (% below running peak)
  - Calmar ratio = annualised return / |max drawdown|
  - Sortino ratio = (mean_return - target) / downside_deviation
  - All historical drawdowns > 10% as peak-trough-recovery triplets
  - Category.RISK_MACRO
"""

from __future__ import annotations

import math
from datetime import date
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

# Minimum price-series length for any computation.
_MIN_PRICES = 2
# Drawdown threshold for "significant" events list.
_SIGNIFICANT_THRESHOLD = 0.10
# Trading days per year (approximate; used for Calmar annualisation).
_TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Core maths
# ---------------------------------------------------------------------------


def _ols_annualised_return(prices: list[float], dates: list[str]) -> float | None:
    """CAGR = (last/first)^(365/calendar_days) - 1.

    Returns None when prices or date span is insufficient.
    """
    if len(prices) < 2:
        return None
    try:
        d0 = date.fromisoformat(dates[0])
        d1 = date.fromisoformat(dates[-1])
    except (ValueError, IndexError):
        return None
    calendar_days = (d1 - d0).days
    if calendar_days <= 0 or prices[0] <= 0:
        return None
    ratio = prices[-1] / prices[0]
    if ratio <= 0:
        return None
    return ratio ** (365.0 / calendar_days) - 1.0


def _compute_drawdown_series(prices: list[float]) -> list[float]:
    """Return drawdown series: dd_t = (price_t - running_max_t) / running_max_t."""
    running_max = prices[0]
    result: list[float] = []
    for p in prices:
        running_max = max(running_max, p)
        result.append((p - running_max) / running_max)
    return result


def _compute_max_drawdown_stats(
    prices: list[float],
    dates: list[str],
) -> dict[str, Any]:
    """Return max drawdown stats for the given price window."""
    if len(prices) < 2:
        return {
            "max_drawdown": None,
            "max_drawdown_peak_date": None,
            "max_drawdown_trough_date": None,
            "max_drawdown_duration_days": None,
            "recovery_date": None,
            "recovery_duration_days": None,
            "currently_in_drawdown": None,
            "current_drawdown": None,
        }

    dd_series = _compute_drawdown_series(prices)
    min_dd = min(dd_series)
    trough_idx = dd_series.index(min_dd)

    # Peak: last date where running max was set before the trough
    running_max = prices[0]
    peak_idx = 0
    for i in range(trough_idx + 1):
        if prices[i] >= running_max:
            running_max = prices[i]
            peak_idx = i

    peak_date = dates[peak_idx]
    trough_date = dates[trough_idx]
    try:
        duration_days = (date.fromisoformat(trough_date) - date.fromisoformat(peak_date)).days
    except ValueError:
        duration_days = None

    # Recovery: first date after trough where price >= peak price
    peak_price = prices[peak_idx]
    recovery_date: str | None = None
    recovery_days: int | None = None
    for i in range(trough_idx + 1, len(prices)):
        if prices[i] >= peak_price:
            recovery_date = dates[i]
            try:
                recovery_days = (
                    date.fromisoformat(recovery_date) - date.fromisoformat(trough_date)
                ).days
            except ValueError:
                recovery_days = None
            break

    current_dd = dd_series[-1]
    return {
        "max_drawdown": round(min_dd, 6),
        "max_drawdown_peak_date": peak_date,
        "max_drawdown_trough_date": trough_date,
        "max_drawdown_duration_days": duration_days,
        "recovery_date": recovery_date,
        "recovery_duration_days": recovery_days,
        "currently_in_drawdown": current_dd < -1e-9,
        "current_drawdown": round(current_dd, 6),
    }


def _compute_calmar(prices: list[float], dates: list[str]) -> float | None:
    """Calmar = annualised_return / |max_drawdown|. None when undefineable."""
    ann = _ols_annualised_return(prices, dates)
    if ann is None:
        return None
    dd_series = _compute_drawdown_series(prices)
    max_dd = min(dd_series)
    if max_dd >= 0:
        # No drawdown at all.
        return None
    return round(ann / abs(max_dd), 4)


def _compute_sortino(
    prices: list[float],
    target_return: float = 0.0,
) -> float | None:
    """Sortino = (mean_daily_return - target) / downside_std.

    Daily returns computed from consecutive prices.
    target_return expressed as a daily return (default 0).
    """
    if len(prices) < 3:
        return None

    daily_returns = [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices))]
    mean_ret = sum(daily_returns) / len(daily_returns)
    downside = [r for r in daily_returns if r < target_return]
    if not downside:
        return None
    downside_var = sum((r - target_return) ** 2 for r in downside) / len(downside)
    downside_std = math.sqrt(downside_var)
    if downside_std < 1e-12:
        return None
    # Annualise both numerator and denominator by sqrt(252)
    ann_excess = (mean_ret - target_return) * _TRADING_DAYS_PER_YEAR
    ann_downside = downside_std * math.sqrt(_TRADING_DAYS_PER_YEAR)
    return round(ann_excess / ann_downside, 4)


def _all_significant_drawdowns(
    prices: list[float],
    dates: list[str],
    threshold: float = _SIGNIFICANT_THRESHOLD,
) -> list[dict[str, Any]]:
    """Return all distinct drawdown events where depth >= threshold.

    Each event: peak, trough, recovery (or None), depth, duration_days, recovery_days.
    """
    if len(prices) < 2:
        return []

    events: list[dict[str, Any]] = []
    n = len(prices)
    i = 0
    while i < n:
        # Scan forward to find a local peak
        peak_val = prices[i]
        peak_idx = i
        # Walk until price starts declining below threshold
        j = i + 1
        while j < n and prices[j] >= peak_val:
            if prices[j] > peak_val:
                peak_val = prices[j]
                peak_idx = j
            j += 1
        if j >= n:
            break

        # Find the trough from here
        trough_val = prices[j]
        trough_idx = j
        k = j + 1
        while k < n:
            if prices[k] < trough_val:
                trough_val = prices[k]
                trough_idx = k
            elif prices[k] >= peak_val:
                # Recovered before deepening further
                break
            k += 1

        depth = (trough_val - peak_val) / peak_val
        if depth <= -threshold:
            # Look for recovery
            recovery_idx: int | None = None
            for m in range(trough_idx + 1, n):
                if prices[m] >= peak_val:
                    recovery_idx = m
                    break

            try:
                dur = (
                    date.fromisoformat(dates[trough_idx]) - date.fromisoformat(dates[peak_idx])
                ).days
            except ValueError:
                dur = None

            rec_days: int | None = None
            rec_date: str | None = None
            if recovery_idx is not None:
                rec_date = dates[recovery_idx]
                try:
                    rec_days = (
                        date.fromisoformat(rec_date) - date.fromisoformat(dates[trough_idx])
                    ).days
                except ValueError:
                    rec_days = None

            events.append(
                {
                    "peak": dates[peak_idx],
                    "trough": dates[trough_idx],
                    "recovery": rec_date,
                    "depth": round(depth, 6),
                    "duration_days": dur,
                    "recovery_days": rec_days,
                }
            )
            # Continue scan from recovery point or end
            i = recovery_idx if recovery_idx is not None else n
        else:
            # Not a significant drawdown; advance
            i = j + 1

    return events


def _window_slice(
    prices: list[float],
    dates: list[str],
    trading_days: int,
) -> tuple[list[float], list[str]]:
    """Return the last `trading_days` data points."""
    if len(prices) <= trading_days:
        return prices, dates
    return prices[-trading_days:], dates[-trading_days:]


# Window definitions: label -> approximate trading days
_WINDOWS: dict[str, int] = {
    "1Y": 252,
    "3Y": 756,
    "5Y": 1260,
    "10Y": 2520,
}


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


def execute(
    prices: list[float],
    dates: list[str],
    target_daily_return: float = 0.0,
) -> dict[str, Any]:
    """Compute drawdown panel from daily price series.

    Args:
        prices: Daily adjusted close prices, oldest first. Min 2 values.
        dates: ISO-8601 date strings aligned with `prices`, oldest first.
        target_daily_return: Minimum acceptable daily return for Sortino denominator
            (default 0.0 — pure downside deviation).

    Returns:
        Dict with:
            price_series_start, price_series_end,
            windows (dict of per-window stats keyed by "1Y"/"3Y"/"5Y"/"10Y"/"full"),
            since_ipo (full-series stats),
            all_drawdowns_gt_10pct (list of significant events from full series),
            underwater_curve (full series, sampled to max 500 points),
            status ("OK" or "DEGRADED"), missing_inputs.

    Raises:
        ValueError: prices or dates is empty, or len(prices) != len(dates).
    """
    if not prices:
        raise ValueError("prices is empty")
    if len(prices) != len(dates):
        raise ValueError(f"prices length {len(prices)} != dates length {len(dates)}")
    if len(prices) < _MIN_PRICES:
        raise ValueError(f"prices must have at least {_MIN_PRICES} values; got {len(prices)}")

    missing: list[str] = []

    # Full series ("since IPO") stats
    since_ipo_stats = _compute_max_drawdown_stats(prices, dates)
    since_ipo_stats["calmar"] = _compute_calmar(prices, dates)
    since_ipo_stats["sortino"] = _compute_sortino(prices, target_daily_return)
    since_ipo_stats["annualised_return"] = _ols_annualised_return(prices, dates)

    # Per-window stats
    window_stats: dict[str, Any] = {}
    for label, td in _WINDOWS.items():
        w_prices, w_dates = _window_slice(prices, dates, td)
        if len(w_prices) < _MIN_PRICES:
            missing.append(f"insufficient_data_for_{label}")
            window_stats[label] = {"status": "DEGRADED", "reason": "insufficient_data"}
            continue
        stats = _compute_max_drawdown_stats(w_prices, w_dates)
        stats["calmar"] = _compute_calmar(w_prices, w_dates)
        stats["sortino"] = _compute_sortino(w_prices, target_daily_return)
        stats["annualised_return"] = _ols_annualised_return(w_prices, w_dates)
        window_stats[label] = stats

    # All significant drawdowns from full series
    all_dd = _all_significant_drawdowns(prices, dates, _SIGNIFICANT_THRESHOLD)

    # Underwater curve — downsample to max 500 points for payload size
    full_dd_series = _compute_drawdown_series(prices)
    if len(full_dd_series) > 500:
        step = len(full_dd_series) // 500
        uw_curve = [
            {"date": dates[i], "dd": round(full_dd_series[i], 6)}
            for i in range(0, len(full_dd_series), step)
        ]
    else:
        uw_curve = [
            {"date": dates[i], "dd": round(full_dd_series[i], 6)}
            for i in range(len(full_dd_series))
        ]

    return {
        "price_series_start": dates[0],
        "price_series_end": dates[-1],
        "since_ipo": since_ipo_stats,
        "windows": window_stats,
        "all_drawdowns_gt_10pct": all_dd,
        "underwater_curve": uw_curve,
        "status": "DEGRADED" if missing else "OK",
        "missing_inputs": missing,
    }


# ---------------------------------------------------------------------------
# Schema registration
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="drawdown_panel",
        category=Category.RISK_MACRO,
        one_liner=(
            "Per-window max drawdown, duration, recovery, Calmar ratio, "
            "Sortino ratio, and all historical drawdowns >10%."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute a full drawdown panel from a daily price series: max drawdown depth, "
            "peak/trough dates, recovery date, Calmar ratio, Sortino ratio, and an "
            "exhaustive list of all historical drawdowns exceeding 10%. "
            "Windowed over 1Y/3Y/5Y/10Y and full since-IPO horizon."
        ),
        when_to_use=[
            "Risk characterisation section of any equity initiation or update.",
            "Comparing drawdown profiles across peers in a sector screen.",
            "Stress-testing a position by understanding worst historical loss and recovery.",
        ],
        when_not_to_use=[
            "Fixed income — drawdown is less meaningful than duration/spread for bonds.",
            "When only a valuation ratio series is available (use historical_multiple_trends).",
            "For single-point risk — use risk_reward_calculator for point-in-time R/R.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "prices": HelperParam(
                type="list[float]",
                required=True,
                description=(
                    "Daily adjusted close prices, oldest first. At least 2 values required."
                ),
            ),
            "dates": HelperParam(
                type="list[str]",
                required=True,
                description=("ISO-8601 date strings aligned 1:1 with prices, oldest first."),
            ),
            "target_daily_return": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description=(
                    "Minimum acceptable daily return for Sortino downside deviation "
                    "(default 0.0). Express as a decimal, e.g. 0.0001 for 0.01%/day."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="drawdown_panel_output",
                type="drawdown_panel_output",
                description=(
                    "price_series_start/end, since_ipo stats, per-window stats (1Y/3Y/5Y/10Y), "
                    "all_drawdowns_gt_10pct list, underwater_curve, status, missing_inputs."
                ),
            ),
        ],
        produces_artifacts=["drawdown_panel_output"],
        consumes_artifacts=["eodhd_eod_prices_output"],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
