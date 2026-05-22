---
name: insider_signal_panel
category: signals
version: 0.1.0
produces_artifacts:
  - insider_signal_output
consumes_artifacts:
  - eodhd_insider_transactions_output
---

# insider_signal_panel — Form 4 Insider Trading Signal

## Purpose

Convert SEC Form 4 insider transactions into a structured buying/selling signal that
distinguishes discretionary conviction trades from routine compensation-related activity.

The helper answers: are the people who know this business best putting their own money
in or taking it out — and is the recent activity a meaningful cluster or just noise?

## When to use

- Initiation reports: add insider conviction context to the investment thesis.
- Update reports post-quarter: check if insiders bought the dip or sold into strength.
- Sector comparisons: cross-company cohort insider activity for a peer group.
- Any time you want to assess management conviction without relying on price action.

## When NOT to use

- Real-time trading decisions — Form 4 filings have a 2-business-day lag; this is
  retrospective context, not a timing tool.
- When the raw transaction data only provides a coarse "buy"/"sell" flag without the
  Form 4 transaction code (P/S/A/M/F...). The code-filtering step is a build-blocker;
  without it, the helper cannot separate discretionary trades from option exercises and
  tax withholding.
- Interpreting insider *selling* as a strong negative signal — selling is close to
  uninformative because of the many non-signal reasons to sell (diversification,
  pre-scheduled 10b5-1 plans, liquidity needs).
- Options/derivative activity — use ft_capital_structure or a dedicated options helper.

## Methodology

### Step 1 — Transaction-code filter

Only discretionary open-market trades enter the signal:

| Code | Meaning | Treatment |
|---|---|---|
| P | Open-market purchase | BUY (signal) |
| S | Open-market or private sale | SELL signal only if standalone (see Step 1b) |
| A | Grant / award / other acquisition | EXCLUDED — compensation noise |
| M | Option exercise | EXCLUDED — derivative monetization |
| F | Tax withholding on vesting | EXCLUDED — not discretionary |
| G | Gift | EXCLUDED |
| C | Conversion of derivative | EXCLUDED |
| D | Disposition to the issuer | EXCLUDED |
| X | Exercise of in-the-money derivative | EXCLUDED |

**Step 1b — Option-exercise netting:** An M (exercise) immediately followed by an S
(sale of the acquired shares) is routine monetization, not a bearish signal. The helper
flags standalone S trades (sale of previously held shares) as the only true sell signal.

**Step 1c — 10b5-1 plan detection:** If the Form 4 footnote references a Rule 10b5-1
plan, the sale is marked `scheduled` and excluded from the bearish signal. Pre-committed
plan sales carry no timing information.

### Step 2 — Aggregate per window

For each lookback window (default 90d / 180d / 365d):
```
net_shares            = buy_shares - sell_shares
net_value             = buy_value  - sell_value
buy_sell_value_ratio  = buy_value / max(sell_value, epsilon)
pct_insiders_buying   = distinct_buyers / distinct_active_insiders
```

### Step 3 — Cluster detection

`cluster_buy_detected = True` if >= 3 distinct insiders make open-market purchases
within any 30-day sub-window. Cluster buying is the most robust insider signal in the
academic literature (Lakonishok & Lee 2001): far more informative than a single large
purchase.

### Step 4 — Role weighting

Default role weights: CEO/CFO = 1.0, President = 0.8, Officer = 0.6, Director = 0.5,
10%-owner = 0.3. A CEO buy that materially increases her own stake (+20% of holdings)
is a stronger conviction signal than a token Director purchase.

```
role_weighted_net_value = sum(buy_value_i * weight_i) - sum(sell_value_i * weight_i)
```

### Step 5 — Signal classification

| Classification | Conditions |
|---|---|
| bullish | cluster_buy AND role_weighted_net > 0 AND pct_buying >= 50% |
| mildly_bullish | net_value > 0 AND at least one buyer |
| neutral | near-zero net_value, or only excluded codes |
| mildly_bearish | net_value < 0, multiple standalone S trades |
| bearish | cluster of standalone officer sales, no offsetting buys |

Signal confidence scales with distinct insider count and dollar magnitude.

## Output schema

The helper produces `insider_signal_output` with:

```json
{
  "windows": {
    "90d": {
      "open_market_buys": {"count": 4, "distinct_insiders": 3, "shares": 52000, "value": 7900000},
      "open_market_sells": {"count": 1, "distinct_insiders": 1, "shares": 8000, "value": 1220000},
      "standalone_sells": 1,
      "net_shares": 44000,
      "net_value": 6680000,
      "buy_sell_value_ratio": 6.4754,
      "pct_insiders_buying": 0.75,
      "cluster_buy_detected": true,
      "role_weighted_net_value": 6010000.0,
      "largest_single_buy": {"insider": "Jane Doe", "role": "CEO", "value": 4500000, "pct_increase_in_holdings": 0.22}
    },
    "180d": {...},
    "365d": {...}
  },
  "signal_classification": "bullish",
  "signal_confidence": "high",
  "excluded_transactions": {"grants_A": 8, "option_exercises_M": 12, "tax_withholding_F": 5},
  "data_as_of": "2026-05-20"
}
```

## Common pitfalls

- **Treating all sells as bearish.** Insider selling has many non-informative causes.
  The helper down-weights or excludes scheduled and compensation-driven sells. The
  narrative must reflect this asymmetry — buying is signal; selling is mostly noise.
- **Over-interpreting a single large buy.** Without cluster confirmation, a single CEO
  purchase may be a PR gesture. Use `cluster_buy_detected` as the primary filter.
- **Missing transaction_code field.** If data only provides a coarse buy/sell label,
  the code-filter cannot operate and signal quality degrades significantly. The helper
  will still compute net values, but the `excluded_transactions` dict will be empty.
- **10%-owner block trades.** A private-equity fund reducing its stake is not
  "insider knowledge" in the executive sense. The 0.3 weight for 10%_owner down-grades
  their contribution; do not present these as executive bearish signals.
- **Sparse data (micro-cap).** With < 3 insiders reporting, cluster detection cannot
  fire. `signal_confidence = "low"` is automatic in these cases.

## Related helpers

- `eodhd_insider_transactions` — upstream data source (wraps EODHD get_insider_transactions)
- `analyst_revision_momentum` — pairs well for a combined conviction picture
- `moving_average_panel` — technical context to complement insider timing
- `historical_multiple_trends` — valuation context for interpreting buy prices
