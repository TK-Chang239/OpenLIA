---
name: historical_multiple_trends
category: signals
version: 0.1.0
produces_artifacts:
  - historical_multiple_trends_output
consumes_artifacts:
  - eodhd_market_cap_history_output
---

# historical_multiple_trends — Historical Valuation Multiple Trends

## Purpose

Place the current valuation multiple in the context of the company's own history
(1Y / 3Y / 5Y / 10Y windows) to distinguish genuine cheapness from a deserved
de-rating, and optionally benchmark against sector peers.

The helper answers: is the stock cheap or expensive relative to how it has historically
traded — and is any gap a mean-reversion opportunity or a structural re-rating?

## When to use

- Initiation reports: frame whether the current multiple is cheap/expensive vs its own
  history before drawing a valuation conclusion.
- Update reports post-earnings: quantify how much the multiple has shifted after a
  guidance cut or beat and what the new percentile implies.
- Sector comparisons: cross-company premium/discount mapping vs sector median trajectory.
- Whenever a low headline multiple might be a value trap vs a genuine discount.

## When NOT to use

- Companies with less than 2 years of public history — insufficient data for
  meaningful trend analysis. The helper will report only available windows.
- Loss-making periods where P/E is NM (not meaningful) — use P/S or EV/Sales instead.
  The helper auto-excludes NM periods from P/E stats and flags them.
- Real-time screener use — this is a historical context tool, not a live valuation model.
- Concluding "cheap" from a low z-score alone — always pair with `margin_trajectory_regression`
  and `roic_panel` to rule out structural deterioration (value trap risk).

## Methodology

### Step 1 — Reconstruct historical series

For each multiple and date (using point-in-time market cap with TTM-as-reported fundamentals):
```
P/E_t    = Market_Cap_t / Net_Income_TTM_t
P/S_t    = Market_Cap_t / Revenue_TTM_t
EV/EBITDA_t = EV_t / EBITDA_TTM_t
P/B_t    = Market_Cap_t / Book_Value_t
```
Loss periods (NI <= 0) produce NM P/E values; these are excluded from P/E statistics
and counted in `nm_periods`. Use P/S or EV/Sales as primary lens during loss periods.

### Step 2 — Descriptive stats per window

For each window (1Y / 3Y / 5Y / 10Y), using ~4 observations per year (quarterly cadence):
- min, p25, median, mean, p75, max, stdev

### Step 3 — Position the current multiple

```
z_score_w         = (current - mean_w) / stdev_w
percentile_rank_w = fraction of historical observations strictly below current
vs_median_pct_w   = (current - median_w) / |median_w|
```

**Warning thresholds:**
- percentile < 10th: near historical low — check for structural impairment.
- percentile > 90th: near historical high — premium must be justified.

### Step 4 — Re-rating vs de-rating trend

OLS slope of the multiple over the longest available window:
- Persistent downward slope = structural de-rating (often justified by decelerating fundamentals)
- Flat series with current below median = mean-reversion candidate
- Persistent upward slope = re-rating (requires earnings acceleration or multiple expansion thesis)

### Step 5 — Sector overlay (optional)

If `sector_median_series` provided, track the stock's premium/discount to sector over time:
```
current_premium_pct = (current_stock_multiple - sector_median) / sector_median
```
A stock can look cheap on absolute history while still expensive vs a sector that has
de-rated further — the relative view captures this.

### Step 6 — Forward/trailing spread (optional)

If `forward_estimates` provided:
```
implied_growth = pe_ttm / pe_forward - 1
```
This is a rough read of embedded growth expectations from analyst consensus.

## Output schema

The helper produces `historical_multiple_trends_output` with:

```json
{
  "pe_ttm": {
    "current": 18.5,
    "history": {
      "5y": {"count": 20.0, "min": 12.0, "p25": 16.0, "median": 21.0, "mean": 21.5, "p75": 26.0, "max": 38.0, "stdev": 5.2},
      "10y": {"...": "..."}
    },
    "z_score_by_window": {"5y": -0.48, "10y": -0.52},
    "percentile_rank_by_window": {"5y": 0.28, "10y": 0.31},
    "vs_median_pct_by_window": {"5y": -0.119, "10y": -0.09},
    "rerating_trend": "de-rating: multiple contracting from ~24.0x to ~18.5x",
    "valuation_read": "28th percentile of 5y history — modestly cheap vs own history.",
    "nm_periods": 0,
    "warnings": []
  },
  "ps_ttm": {"...": "..."},
  "forward_vs_trailing": {
    "multiple": "pe",
    "forward_value": 15.8,
    "trailing_value": 18.5,
    "implied_growth": 0.171,
    "read": "Forward multiple 15.8x vs trailing 18.5x implies ~17.1% growth in the denominator."
  },
  "nm_periods_flagged": [],
  "mean_reversion_caveat": "A low z-score or percentile is only an opportunity if the business has not structurally changed...",
  "data_as_of": "2026-05-20"
}
```

## Common pitfalls

- **Equating low z-score with "cheap."** Never do this unprompted. The required
  framing is conditional: *below its own history, which is an opportunity only if
  growth/margins/returns are intact* — otherwise it is a value trap. The helper emits
  `mean_reversion_caveat` as a reminder.
- **Ignoring NM periods.** Loss-making quarters make P/E spike or go negative. The
  helper excludes these from stats and flags them in `nm_periods_flagged`. Report the
  flag and recommend P/S or EV/Sales as the primary lens for affected periods.
- **Capital structure changes distorting comparisons.** Large debt issuances or
  buybacks shift P/E and P/B mechanically. EV/EBITDA is more stable across capital
  structures — note when divergence is structural.
- **Insufficient history for requested windows.** A 3-year-old public company has
  no 10Y window. The helper reports only available windows; do not extrapolate a
  10Y stat from 2Y of data.
- **Confusing quarterly cadence with annual.** The helper treats history as quarterly
  by default (4 obs/year). If the caller provides annual data, set `windows_years`
  accordingly or note the cadence mismatch.

## Related helpers

- `comparables_run` — sector/peer multiples for the sector overlay input
- `margin_trajectory_regression` — pairs for value-trap check (is margin structurally declining?)
- `roic_panel` — pairs for value-trap check (is ROIC deteriorating?)
- `moving_average_panel` — tie-in: use `series_kind="multiple"` to smooth P/E time series
- `eodhd_market_cap_history` — upstream market cap series
- `eodhd_income_statement` — upstream EPS/revenue series for denominator reconstruction
