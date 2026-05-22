# Equity Research Engine — Three New Helpers (Spec Addendum)

**Date:** 2026-05-21
**Companion to:** `2026-05-21-equity-research-helpers-design.md`
**Status:** Design spec for review

These three helpers extend the existing stack:

- **`insider_signal_panel`** — insider trading signals from disclosed SEC Form 4 data
- **`moving_average_panel`** — historical moving-average trend, crossovers, and mean-reversion stretch
- **`historical_multiple_trends`** — historical P/E and P/S trends vs the company's own history and sector

Suggested placement: `insider_signal_panel` in **§4 (Business quality / capital allocation)**; `moving_average_panel` in **§5 (Risk + macro)** alongside `drawdown_panel`; `historical_multiple_trends` in **§3 (Valuation)** of the parent helpers-design doc. All follow the §1.1 registration pattern, §1.3 provenance fields, and §1.4 fail-soft policy.

---

## 1. `insider_signal_panel`

**Purpose:** Convert disclosed SEC Form 4 insider transactions into a structured buying/selling signal, properly filtered by transaction type and weighted by insider role.

**Question answered:** Are the people who know this business best putting their own money in or taking it out — and is the recent activity a meaningful cluster or just routine compensation noise?

**Report types:** Initiation (thesis support), Update (post-quarter / event-driven), Sector (cross-company cohort comparison).

**Inputs:**
- `transactions` (list[dict], required): from `eodhd_insider_transactions`. Each: `{date, insider_name, role, transaction_code, shares, price_per_share, value, shares_owned_after}`
- `lookback_windows` (list[int], optional, default `[90, 180, 365]`): trailing day windows to summarize
- `current_price` (float, optional): for marking-to-market open-market buys
- `shares_outstanding` (float, optional): to scale net activity vs float
- `role_weights` (dict, optional): default `{"CEO": 1.0, "CFO": 1.0, "President": 0.8, "Officer": 0.6, "Director": 0.5, "10%_owner": 0.3}`

**Source:** `eodhd_insider_transactions` (wraps `get_insider_transactions`, SEC Form 4).

**Output:**
```json
{
  "windows": {
    "90d": {
      "open_market_buys": {"count": 4, "distinct_insiders": 3, "shares": 52000, "value": 7900000},
      "open_market_sells": {"count": 1, "distinct_insiders": 1, "shares": 8000, "value": 1220000},
      "net_shares": 44000,
      "net_value": 6680000,
      "buy_sell_value_ratio": 6.48,
      "pct_insiders_buying": 0.75,
      "cluster_buy_detected": true,
      "role_weighted_net_value": 6010000,
      "largest_single_buy": {"insider": "CEO Jane Doe", "value": 4500000, "pct_increase_in_holdings": 0.22}
    },
    "180d": { "...": "..." },
    "365d": { "...": "..." }
  },
  "signal_classification": "bullish | mildly_bullish | neutral | mildly_bearish | bearish",
  "signal_confidence": "high | moderate | low",
  "excluded_transactions": {"option_exercises_M": 12, "grants_A": 8, "tax_withholding_F": 5, "gifts_G": 1},
  "narrative": "Three distinct insiders, including the CEO and CFO, made open-market purchases totaling $7.9M over 90 days — a cluster buy. The CEO purchase increased her holdings 22%. No discretionary sales. Strongest insider signal in the trailing year.",
  "data_as_of": "2026-05-20",
  "source_provenance": ["form4:0001234567-26-000123", "..."]
}
```

**Algorithm:**

**Step 1 — Transaction-code filter (the make-or-break step).** Classify every Form 4 transaction by code; only discretionary open-market trades enter the signal:

```
INFORMATIVE (signal):
  P  = open-market or private PURCHASE   -> BUY
  S  = open-market or private SALE       -> SELL (weak signal; see weighting)

EXCLUDED (not discretionary signals; counted only in excluded_transactions):
  A  = grant / award / other acquisition (compensation)
  M  = exercise of derivative (option exercise)
  F  = shares withheld to cover tax on vesting
  G  = gift
  C  = conversion of derivative
  D  = disposition to the issuer
  X  = exercise of in-the-money/at-the-money derivative
```

A common refinement: an **M** (option exercise) immediately followed by an **S** (sale of the acquired shares) is routine monetization, *not* a bearish signal — net these out rather than logging the S as a discretionary sale. Flag standalone S (sale of previously held shares) as the only true sell signal.

**Step 2 — Aggregate per window**, separately for buys and sells:
```
net_shares       = buy_shares - sell_shares
net_value        = buy_value  - sell_value
buy_sell_value_ratio = buy_value / max(sell_value, epsilon)
pct_insiders_buying  = distinct_buyers / distinct_active_insiders
```

**Step 3 — Cluster detection.** `cluster_buy_detected = True` if >= 3 distinct insiders make open-market *purchases* within any 30-day sub-window. Cluster buying is the most robust signal in the academic literature (Lakonishok & Lee 2001; later confirmation work) — far more informative than a single large buy.

**Step 4 — Role weighting and conviction sizing:**
```
role_weighted_net_value = sum over buys (value_i * role_weight_i) - sum over sells (value_i * role_weight_i)
pct_increase_in_holdings_i = shares_bought_i / max(shares_owned_before_i, epsilon)
```
CEO/CFO purchases carry the most information; a buy that materially increases an insider's own stake (e.g., +20%) is a stronger conviction signal than a token purchase.

**Step 5 — Signal classification** (heuristic, configurable thresholds):
```
bullish:        cluster_buy_detected AND role_weighted_net_value > 0 AND pct_insiders_buying >= 0.5
mildly_bullish: net_value > 0 AND (CEO or CFO among buyers)
neutral:        |net_value| small relative to typical activity, or only excluded codes present
mildly_bearish: net_value < 0 with multiple standalone S transactions by officers
bearish:        cluster of standalone officer sales with no offsetting buys
```
`signal_confidence` scales with number of distinct insiders and dollar magnitude relative to the company's float.

**Edge cases:**
- All activity is A/M/F (pure compensation): `signal_classification = "neutral"`, narrative notes "no discretionary trading."
- 10%-owner block trades (often funds rebalancing, not "insider" knowledge): down-weighted via `role_weights`; flag separately so a private-equity exit isn't read as an executive's bearish view.
- Rule 10b5-1 plan sales (pre-scheduled): if the Form 4 footnote flags a 10b5-1 plan, mark the sale as `scheduled` and exclude from the bearish signal — these are pre-committed and carry no timing information.
- Sparse data (micro-cap, few insiders): `signal_confidence = "low"`; do not over-interpret a single trade.

**Verifier hooks:**
- `temporal_ambiguous`: any insider claim in prose must state the window ("over the trailing 90 days").
- `numeric_inconsistency`: net_value / counts in prose match output.
- `citation_missing`: each material transaction cited to its Form 4 accession number.
- `source_tier_insufficient` (future): insider claims must trace to PRIMARY (SEC Form 4), not aggregator summaries.

**Note on interpretation (for the narrative generator):** Insider *buying* is a modestly predictive positive signal in the literature; insider *selling* is close to uninformative because of the many non-signal reasons to sell. The narrative should never present selling with the same weight as buying, and should never imply certainty — this is one input to a thesis, not a verdict.

**Build note:** Confirm early whether `eodhd_insider_transactions` returns the raw Form 4 transaction *code* (P/S/A/M/F) or only a pre-bucketed buy/sell flag. If it only gives a coarse buy/sell, you lose the ability to strip out option exercises and tax withholding and the signal degrades badly — this field is a build-blocker for the code-filtering step.

---

## 2. `moving_average_panel`

**Purpose:** Derive the moving-average trend state, crossover signals, and mean-reversion stretch that analysts cite for timing and context — built on top of the raw indicator series from `eodhd_technicals`.

**Question answered:** What trend regime is the stock in, where does price sit relative to its key moving averages, and is it stretched far enough from trend to matter?

**Report types:** Update (timing / "where does the stock sit now"), Initiation (technical context section), Sector (cross-company trend-regime cohort: how many names are above their 200-day).

**Why this is a helper and not just `eodhd_technicals`:** §2.1 already exposes raw SMA/EMA series. This helper adds the *derived states and signals* an analyst actually writes about — price-vs-MA position, MA slope/trend regime, golden/death crosses with recency, and distance-from-MA — so the LLM cites a structured verdict rather than re-deriving it from a raw series (and getting the crossover lookback wrong).

**Inputs:**
- `price_series` (Series, required): daily (or weekly) **split/dividend-adjusted** close prices, ascending by date. From `eodhd_historical_stock_prices`.
- `ma_windows` (list[int], optional, default `[20, 50, 100, 200]`): MA lengths in periods.
- `ma_type` (str, optional, default `"sma"`): `"sma"` | `"ema"`.
- `crossover_pairs` (list[tuple], optional, default `[(50, 200), (20, 50)]`): (fast, slow) pairs to test for crosses.
- `volume_series` (Series, optional): to confirm crosses on volume.
- `series_kind` (str, optional, default `"price"`): `"price"` | `"multiple"` — see tie-in note below.

**Source:** Raw MA values can come from `eodhd_technicals` (`get_technical_indicators`); price series from `eodhd_historical_stock_prices`. Helper computes the derived signals.

**Output:**
```json
{
  "as_of": "2026-05-20",
  "current_price": 150.0,
  "ma_type": "sma",
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
      "return_since_cross_pct": 0.230, "still_in_effect": true,
      "confirmed_on_volume": true
    },
    {
      "pair": "20/50", "type": "golden_cross", "date": "2026-04-30",
      "days_ago": 20, "price_at_cross": 145.0,
      "return_since_cross_pct": 0.034, "still_in_effect": true
    }
  ],
  "distance_from_ma": {
    "200d_stretch_pct": 0.142,
    "200d_stretch_zscore": 1.35,
    "stretch_read": "14% above the 200-day, ~1.3 sigma vs its own history — extended but not extreme"
  },
  "trend_classification_narrative": "Price sits above all four moving averages in a bullish stack (20>50>100>200), all rising or flat. The 50/200 golden cross from Nov-2025 remains in effect (+23% since). The stock is ~14% above its 200-day, modestly stretched.",
  "data_as_of": "2026-05-20"
}
```

**Algorithm:**

**Step 1 — Compute / ingest MAs.** For each window `n`:
```
SMA_n(t) = mean(price[t-n+1 .. t])
EMA_n(t) = price[t]*k + EMA_n(t-1)*(1-k),  where k = 2/(n+1)
```
Require at least `n` observations before reporting `MA_n`; otherwise mark that window `null` (do not back-pad with partial windows — a 200-day MA needs 200 points).

**Step 2 — Price-vs-MA position and MA slope:**
```
price_vs_ma_pct_n = current_price / MA_n - 1
slope_pct_per_period_n = (MA_n(t) - MA_n(t-k)) / MA_n(t-k) / k     # default k = 20 periods
slope_state: rising  if slope > +threshold
             falling if slope < -threshold
             flat/flattening otherwise   (threshold default ~0.05%/period)
```

**Step 3 — MA stack and trend regime:**
```
ma_stack = "bullish"  if MA_20 > MA_50 > MA_100 > MA_200
           "bearish"  if MA_20 < MA_50 < MA_100 < MA_200
           "mixed"    otherwise
trend_regime = "uptrend"   if price > MA_200 AND MA_200 slope >= 0
               "downtrend" if price < MA_200 AND MA_200 slope <= 0
               "transition / range" otherwise
```
The 200-day and its slope are the primary trend anchor; the stack adds confirmation.

**Step 4 — Crossover detection.** For each (fast, slow) pair, scan the MA series for sign changes of `(MA_fast - MA_slow)`:
```
golden_cross: MA_fast crosses ABOVE MA_slow   (fast-MA[t-1] <= slow-MA[t-1] AND fast-MA[t] > slow-MA[t])
death_cross:  MA_fast crosses BELOW MA_slow
```
Report the most recent cross per pair with date, days_ago, price_at_cross, return_since_cross, and `still_in_effect` (true if the fast MA remains on the same side). If `volume_series` supplied, set `confirmed_on_volume = True` when cross-period volume exceeds its trailing average (a volume-confirmed cross is the only version with much evidentiary weight).

**Step 5 — Distance-from-MA / mean-reversion stretch:**
```
200d_stretch_pct = current_price / MA_200 - 1
200d_stretch_zscore = (stretch_pct - mean(historical stretch_pct)) / stdev(historical stretch_pct)
```
The z-score is the meaningful one: "+14% above the 200-day" means little without knowing this stock routinely runs +20%. A high positive stretch z-score flags a name extended above trend (pullback risk); a deep negative one flags oversold-vs-trend.

**Edge cases:**
- Series shorter than the longest `ma_window`: that MA returns `null`; trend_regime falls back to the longest available MA with a caveat. A 6-month-old IPO has no 200-day MA — do not fabricate one.
- Choppy / range-bound series: crossovers whipsaw (rapid golden/death alternation). Detect via crossover frequency in the window; if > N crosses in the period, set `trend_regime = "range"` and flag crosses as low-reliability.
- Stock splits / large dividends: ensure `price_series` is split/dividend-adjusted before computing MAs, or crosses will be spurious. Use the adjusted close from `eodhd_historical_stock_prices`.
- Weekly vs daily: MA windows are in *periods*, not days — state the period basis in output so "50" isn't misread as 50 days on a weekly series.

**Verifier hooks:**
- `temporal_ambiguous`: any MA/cross claim in prose must state the window and basis ("the 50/200-day golden cross", "the 200-day SMA").
- `numeric_inconsistency`: MA values, price-vs-MA %, and cross dates in prose match output (and reconcile with `eodhd_technicals` within tolerance — same drift check as §2.2).
- `block_shape`: each requested `ma_window` present (or explicitly `null`) and each `crossover_pair` reported.
- `numeric_ungrounded` (future): "trading above its 200-day" must trace to the computed `price_above_ma`, not asserted.

**Note for the narrative generator (important):** A moving-average crossover is **context, not a verdict.** The golden/death cross is widely cited but its standalone predictive value is weak and regime-dependent — it works in trending markets and whipsaws in ranges. The narrative must (a) never present a cross as a buy/sell signal on its own, (b) prefer volume-confirmed crosses, and (c) frame stretch and trend as conditional on the fundamental thesis from the rest of the report. This is the same conditional-language discipline enforced on insider selling (§1) and multiple z-scores (§3).

**Tie-in — smoothing the valuation multiple:** With `series_kind: "multiple"`, apply this same MA logic to the multiple series from `historical_multiple_trends` (§3) rather than to price. A 1-year moving average of trailing P/E damps quarter-to-quarter EPS noise and makes the re-rating/de-rating trend (§3, Step 4) cleaner than a raw point-in-time series. Keep the two distinct in output: price MAs are timing/technical context; smoothed-multiple MAs are a valuation-trend refinement.

---

## 3. `historical_multiple_trends`

**Purpose:** Place the current valuation multiple in the context of the company's own history (and its sector), to distinguish genuine cheapness from a deserved de-rating.

**Question answered:** Is the stock cheap or expensive relative to how it has historically traded — and is any gap a mean-reversion opportunity or a structural re-rating?

**Report types:** Initiation (valuation framing), Update (post-earnings multiple shift), Sector (cross-company premium/discount mapping).

**Inputs:**
- `ticker` (str, required)
- `multiples` (list[str], optional, default `["pe_ttm", "ps_ttm", "ev_ebitda", "pb"]`)
- `history_years` (int, optional, default `10`)
- `windows` (list[int], optional, default `[1, 3, 5, 10]`): year windows for stats
- `sector_median_series` (dict, optional): peer/sector median multiple time series, for relative analysis
- `forward_estimates` (optional): from `eodhd_earnings_trends`, to compute forward multiples and the forward/trailing spread

**Source:** Reconstruct historical multiples from `eodhd_historical_market_cap` (market cap series) / historical EPS/revenue/EBITDA/book value from `eodhd_statements`; or use EODHD historical valuation ratios directly if available. Current values from `eodhd_ratios`.

**Output:**
```json
{
  "as_of": "2026-05-20",
  "pe_ttm": {
    "current": 18.5,
    "history": {
      "5y": {"min": 12.0, "p25": 16.0, "median": 21.0, "mean": 21.5, "p75": 26.0, "max": 38.0, "stdev": 5.2},
      "10y": {"...": "..."}
    },
    "z_score_5y": -0.48,
    "percentile_rank_5y": 0.28,
    "vs_5y_median_pct": -0.119,
    "rerating_trend": "de-rating: 5y multiple has compressed from ~24x to ~18x",
    "valuation_read": "below own 5y median (28th percentile), but inside one stdev — modestly cheap, not extreme"
  },
  "ps_ttm": { "...": "..." },
  "relative_to_sector": {
    "current_premium_to_sector_pct": -0.15,
    "historical_avg_premium_pct": 0.05,
    "premium_trend": "stock has moved from a 5% premium to a 15% discount vs sector over 3 years"
  },
  "forward_vs_trailing": {
    "pe_forward": 15.8, "pe_ttm": 18.5,
    "implied_eps_growth": 0.171,
    "read": "forward multiple well below trailing implies the market expects ~17% EPS growth"
  },
  "nm_periods_flagged": ["FY20 (EPS near zero — P/E not meaningful)"],
  "mean_reversion_caveat": "A low z-score is only an opportunity if the business has not structurally changed. Verify growth/margin trajectory before reading the discount as cheap.",
  "data_as_of": "2026-05-20"
}
```

**Algorithm:**

**Step 1 — Reconstruct the historical series.** For each multiple and date:
```
P/E_t  = Market_Cap_t / Net_Income_TTM_t      (or Price_t / EPS_TTM_t)
P/S_t  = Market_Cap_t / Revenue_TTM_t
EV/EBITDA_t = EV_t / EBITDA_TTM_t
P/B_t  = Market_Cap_t / Book_Value_t
```
Use point-in-time market cap with TTM-as-reported fundamentals. Flag the look-ahead caveat: TTM denominators reflect figures reported *after* the price date; for strict point-in-time accuracy use the fundamentals known as of each date, but TTM-as-reported is the common practical convention.

**Step 2 — Per-window descriptive stats:** min, p25, median, mean, p75, max, stdev over each window.

**Step 3 — Position the current multiple:**
```
z_score_w        = (current - mean_w) / stdev_w
percentile_rank_w = fraction of historical observations below current
vs_median_pct_w  = (current - median_w) / median_w
```

**Step 4 — Re-rating vs de-rating trend:** OLS slope of the multiple over the window. A persistent downward slope = structural de-rating (often justified by decelerating fundamentals); a flat series with current below median = mean-reversion candidate. (Optionally smooth the series first via `moving_average_panel` with `series_kind: "multiple"` — see §2 tie-in.)

**Step 5 — Relative-to-sector overlay** (if `sector_median_series` provided): track the stock's premium/discount to its sector over time. The institutional "relative multiple" view — a stock can look cheap on absolute history while still expensive vs a sector that has de-rated further.

**Step 6 — Forward/trailing spread** (if estimates available): `implied_growth ~= pe_ttm / pe_forward - 1` as a rough read of embedded growth expectations.

**Edge cases (critical for P/E):**
- **Loss-making / near-zero EPS periods:** P/E explodes or goes negative and is meaningless. Flag these periods as `NM` (not meaningful), exclude from P/E stats, and recommend P/S or EV/Sales as the primary lens for the affected span. This is the single most common failure mode of historical-P/E analysis.
- **One-time items distorting EPS:** offer an adjusted-EPS variant using `one_time_item_identification` (§4.10) output so the multiple history isn't whipsawed by impairments/charges.
- **Capital-structure change** (large debt issuance/buyback): P/E and P/B shift mechanically; EV/EBITDA is more stable across capital structures — note when divergence is structural rather than valuation-driven.
- **Insufficient history** (recent IPO): report only available windows; do not extrapolate a 10y stat from 2y of data.

**Verifier hooks:**
- `temporal_ambiguous`: every multiple claim must state the window ("vs its 5-year median").
- `numeric_inconsistency`: current multiple and z-score in prose match output and match `eodhd_ratios`.
- `block_shape`: each requested multiple present with current + at least one window of stats.
- `numeric_ungrounded` (future): "trades at a discount to history" must trace to the computed percentile/z-score, not asserted.

**Note for the narrative generator:** Never equate a low z-score with "cheap" unprompted. The required framing is conditional: *below its own history, which is an opportunity only if [growth/margins/returns] are intact* — otherwise it is a value trap. Pair this helper with `margin_trajectory_regression` (§4.13) and `roic_panel` (§4.1) before drawing a buy conclusion.

---

## Summary — how these three interlock with the existing stack

| New helper | Purpose | Pairs with | Primary report use |
|---|---|---|---|
| `insider_signal_panel` | Form 4 buying/selling signal, code-filtered & role-weighted | `analyst_revision_momentum` | Initiation, Update |
| `moving_average_panel` | MA trend regime, crossovers, mean-reversion stretch | `drawdown_panel` (§5.1), `eodhd_technicals` (§2.1), `historical_multiple_trends` (multiple-smoothing) | Update, Initiation, Sector |
| `historical_multiple_trends` | Current P/E & P/S vs own history (z-score, percentile, re-rating) | `comparables` (§3.1), `margin_trajectory_regression` (§4.13), `moving_average_panel` | Initiation, Update, Sector |

All three are **modest, contextual signals**, not verdicts. The verifier and narrative layers should enforce conditional language — especially for insider selling, moving-average crossovers, and low multiple z-scores — so the engine never overstates a single technical or sentiment input.
