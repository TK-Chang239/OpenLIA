---
name: moving_average_panel
category: signals
version: 0.1.0
produces_artifacts:
  - moving_average_panel_output
consumes_artifacts:
  - eodhd_eod_prices_output
---

# moving_average_panel — MA Trend Regime, Crossovers, Mean-Reversion Stretch

## Purpose

Derive the moving-average trend state and derived signals an analyst writes about:
price-vs-MA position, MA slope and trend regime, golden/death crosses with recency,
volume confirmation, and distance-from-MA z-score.

The helper answers: what trend regime is the stock in, where does price sit relative
to its key moving averages, and is it stretched far enough from trend to matter?

Why this is a helper and not just `eodhd_technicals`: §2.1 of the helpers design doc
already exposes raw SMA/EMA series. This helper adds the *derived states and signals*
an analyst actually writes about — price-vs-MA position, MA slope/trend regime,
golden/death crosses with recency, and z-score stretch — so the LLM cites a structured
verdict rather than re-deriving it from a raw series.

## When to use

- Update reports: establish timing/technical context alongside fundamental analysis.
- Initiation reports: add a technical backdrop section for entry context.
- Sector comparisons: count names above their 200-day for a trend-regime cohort view.
- Smoothing valuation multiples: pass `series_kind="multiple"` to apply MA logic to a
  P/E series from `historical_multiple_trends`, dampening quarter-to-quarter EPS noise.

## When NOT to use

- Standalone buy/sell signals — a golden cross has weak standalone predictive value
  and whipsaws in range-bound markets. Always combine with fundamental analysis.
- Series shorter than 20 data points — most requested MA windows will be null.
- Short-term intraday patterns — use `eodhd_intraday`; this helper is for daily/weekly.
- Fabricating MAs from partial windows — a 200-day MA requires 200 data points;
  the helper marks that window null rather than back-padding.

## Methodology

### Step 1 — Compute MAs

For each window n, using split/dividend-adjusted close prices ascending by date:
```
SMA_n(t) = mean(price[t-n+1 .. t])
EMA_n(t) = price[t]*k + EMA_n(t-1)*(1-k)   where k = 2/(n+1)
```
First n-1 values are None (not reported). An IPO stock with 120 days of history
will have null for 200-day MA — the helper does not fabricate it.

### Step 2 — Price-vs-MA position and slope

```
price_vs_ma_pct_n = current_price / MA_n - 1
slope_pct_per_period = (MA_n(t) - MA_n(t-20)) / MA_n(t-20) / 20
```
Slope state: rising if slope > +0.05%/period, falling if < -0.05%/period,
flattening otherwise.

### Step 3 — MA stack and trend regime

```
ma_stack:
  bullish  if MA_20 > MA_50 > MA_100 > MA_200
  bearish  if MA_20 < MA_50 < MA_100 < MA_200
  mixed    otherwise

trend_regime:
  uptrend           if price > MA_200 AND MA_200 slope >= 0
  downtrend         if price < MA_200 AND MA_200 slope <= 0
  transition_or_range  otherwise
```
The 200-day is the primary trend anchor; the stack provides confirmation.

### Step 4 — Crossover detection

For each (fast, slow) pair, scan for sign changes of (MA_fast - MA_slow):
```
golden_cross: MA_fast[t-1] <= MA_slow[t-1] AND MA_fast[t] > MA_slow[t]
death_cross:  MA_fast[t-1] >= MA_slow[t-1] AND MA_fast[t] < MA_slow[t]
```
Reports the most recent cross per pair: date, days_ago, price_at_cross,
return_since_cross, still_in_effect.

Volume confirmation: if `volume_series` supplied, `confirmed_on_volume = True`
when cross-period volume exceeds its 20-period trailing average. A volume-confirmed
cross is the only version with meaningful evidentiary weight.

### Step 5 — Distance-from-MA / mean-reversion stretch

```
200d_stretch_pct    = current_price / MA_200 - 1
200d_stretch_zscore = (stretch_pct - mean(historical stretch_pct)) / stdev(...)
```
The z-score is the meaningful number: "+14% above the 200-day" has no context
without knowing this stock routinely runs +20%. A high positive z-score flags
extended-above-trend (pullback risk); deep negative flags oversold-vs-trend.

## Output schema

The helper produces `moving_average_panel_output` with:

```json
{
  "as_of": "2026-05-20",
  "current_price": 150.0,
  "ma_type": "sma",
  "series_kind": "price",
  "moving_averages": {
    "20":  {"value": 148.2, "price_vs_ma_pct": 0.012, "slope_pct_per_period": 0.0008, "slope_state": "rising"},
    "50":  {"value": 142.5, "price_vs_ma_pct": 0.053, "slope_pct_per_period": 0.0011, "slope_state": "rising"},
    "100": {"value": 138.0, "price_vs_ma_pct": 0.087, "slope_pct_per_period": 0.0006, "slope_state": "rising"},
    "200": {"value": 131.4, "price_vs_ma_pct": 0.142, "slope_pct_per_period": 0.0003, "slope_state": "flattening"}
  },
  "price_above_ma": {"20": true, "50": true, "100": true, "200": true},
  "ma_stack": "bullish",
  "trend_regime": "uptrend",
  "crossovers": [
    {
      "pair": "50/200", "type": "golden_cross", "date": "2025-11-12",
      "days_ago": 189, "price_at_cross": 122.0,
      "return_since_cross_pct": 0.23, "still_in_effect": true, "confirmed_on_volume": true
    }
  ],
  "distance_from_ma": {
    "200d_stretch_pct": 0.142,
    "200d_stretch_zscore": 1.35,
    "stretch_read": "14.2% above 200-day — moderately extended, ~1.4 sigma."
  },
  "trend_classification_narrative": "Price is above 4/4 available moving averages. MA stack: bullish. Trend regime: uptrend. Most recent crossover: golden_cross on 50/200 (2025-11-12)."
}
```

## Common pitfalls

- **Presenting a golden cross as a buy signal.** A crossover is context, not a verdict.
  The 50/200 golden cross is widely cited but its standalone predictive value is weak
  and regime-dependent. The narrative must frame it as conditional technical context.
- **Ignoring volume confirmation.** A low-volume crossover is far less reliable than a
  high-volume one. Always prefer `confirmed_on_volume = True` crosses.
- **Unadjusted prices causing spurious crosses.** Stock splits and large dividends create
  false crosses if unadjusted prices are used. Always pass split/dividend-adjusted close.
- **IPO or short-history stocks.** If the series is shorter than the longest MA window
  (e.g., 200 bars), the 200-day MA will be null. Do not present it in the report.
- **Confusing period basis.** MA windows are in *periods* (data points), not calendar days.
  On weekly data, "50" means 50 weeks (~1 year), not 50 days. The output states `series_kind`
  so the LLM does not misread the time basis.

## Related helpers

- `eodhd_technical_indicators` — upstream raw SMA/EMA series
- `eodhd_eod_prices` — upstream split-adjusted price series
- `historical_multiple_trends` — tie-in: use `series_kind="multiple"` to smooth P/E series
- `insider_signal_panel` — pairs well for timing + conviction context
- `drawdown_panel` — companion risk/technical helper (PR 2.5 risk bundle)
