# Retail Sentiment — backend gaps from UI remake (2026-05-08)

The Retail Sentiment page UI was rebuilt in `ui-remake` to match the
`OpenLIAv3` design language and to surface every spec'd feature
(`planning/specs/pages/departments/RetailSentimentPageSpec.md`) plus the
information from `sentiment_dashboard_design.md`. The UI now has
placeholders / "backend gap" markers wherever it expects data the backend
does not yet provide. This file enumerates the gaps so they can be picked up
in dedicated sessions.

## Gap 1 — `stock_quote` field on `RsSnapshot` — RESOLVED 2026-05-08

**Resolution:** Built sibling endpoint `GET /api/departments/retail_sentiment/
dashboard/quotes?ticker=X&days=N` returning `{ ticker, bars: Array<{ date,
close, daily_change_pct, cumulative_pct }> }`. Implemented in
`packages/core/src/openlia/retail_sentiment/quotes.py` (direct EODHD
`get_eod_historical_stock_market_data` call, defaults to `.US` exchange,
returns `[]` when `EODHD_API_KEY` is unset). Frontend wired via
`useRsQuotes` hook + `SentimentPriceOverlay` chart, replacing the prior
sentiment-only `SentimentLine` and the standalone `BuzzBars` panel
(buzz now renders as faint background bars on the overlay).

**Original ask:** Sentiment-vs-price dual-axis overlay is the canonical
"Sentiment Score" chart per design doc. Without it, the Overview chart shows
sentiment-only.

## Gap 2 — Per-source breakdown by platform

**Why:** Spec calls for cross-platform validation (StockTwits / Twitter / Reddit
/ news) and the Insights "How much should I trust this signal?" question.
Today's `source_breakdown` is a flat `{source_key: count}` dict that doesn't
surface platform identity.

**Shape needed:** `RsSnapshot.source_breakdown: Record<string,
{ count: number; sentiment_mean: number; engagement: number }>` keyed on
canonical platform names: `eodhd_news`, `x_social`, `fmp_stocktwits`,
`fmp_reddit`, `fmp_yahoo`, `fmp_twitter`.

**UI hook:** Today's hero "Sources" stat counts dict keys. Future: a "Source
mix" panel showing per-platform polarity bars in the Overview tab and a
"Cross-source agreement" radial in the Insights tab.

## Gap 3 — Per-evidence-item rows for Evidence feed

**Why:** Spec's Evidence tab + design doc's "Evidence snapshots" both show
per-article / per-tweet rows with: source name, summary text, classification
badge (bull/bear/neutral), additive impact value (e.g. `+0.13`), and raw API
field values. Today's Evidence feed is just snapshot history — no per-source
rows.

**Shape needed:** `GET /api/departments/retail_sentiment/evidence?ticker=X&
days=N` returning:
```json
{
  "items": [
    {
      "id": "uuid",
      "captured_at": "...",
      "ticker": "AAPL",
      "source": "eodhd_news",
      "headline": "Tesla Q1 deliveries beat estimates",
      "url": "...",
      "classification": "bullish" | "bearish" | "neutral",
      "engagement": { "likes": 0, "shares": 0, "comments": 0 },
      "impact_on_sentiment": 0.13,
      "raw_fields": { "normalized": 0.35, "count": 220 }
    }
  ]
}
```

**UI hook:** `EvidenceTab → "Evidence feed"` panel — currently shows a
"Backend gap: per-source rows ... not yet implemented" marker and falls back
to snapshot rows.

## Gap 4 — Score impact decomposition: per-evidence additive bars

**Why:** Design doc section "Score Impact Walkthrough" describes a horizontal
bar chart where each row is a discrete piece of evidence and the rightmost
total equals the snapshot's composite score (Baseline + Δ + Δ + ... = Final).

**Shape needed:** Same evidence endpoint as Gap 3 — the `impact_on_sentiment`
field per item is the bar width, and the running sum derives the chart. UI
already renders the bar layout; only data binding is missing.

**UI hook:** `EvidenceTab → "Score impact decomposition"` panel — currently
renders per-metric bars (closest available substitute) with a backend-gap note.

## Gap 5 — Narrative theme clustering

**Why:** Design doc's "Word themes" chart and "Narrative tracker" patterns
require named themes (e.g. "Small modular nuclear", "Power-supply AI infra")
with stage labels (emerging / peaking / cooling / fading), constituent
tickers, and momentum / breadth metrics.

**Shape needed:** Two candidate endpoints —
1. `GET /api/departments/retail_sentiment/word_weights?ticker=X&from=...&to=...`
   → returns weighted phrase list (proxies EODHD `/api/news-word-weights`).
2. `GET /api/departments/retail_sentiment/narratives?days=7` → returns
   `{ themes: Array<{ id, name, stage, momentum_pct, breadth_count, tickers,
   sparkline: number[] }> }`.

**UI hook:** Currently no UI for narrative themes — slot is reserved on the
Overview page (the design doc's column-3 "Narrative tracker" is intentionally
omitted from this turn).

## Gap 6 — 30-day buzz baseline

**Why:** Design doc's "Buzz Volume" bar chart color-codes each day by ratio
to the 30-day moving average (≤1× neutral, 1–1.5× elevated, >1.5× spike) with
a dashed reference line at the 30d mean. Today's `buzz_volume` field is
already documented as `count_today / mean(count_30d)`, so the underlying
math exists — but a 30-day guarantee should be explicit so the UI can flag
"insufficient baseline" cold-start.

**Shape needed:** `RsSnapshot.buzz_baseline_days: number` (count of days the
30d window actually contains). UI shows "Insufficient baseline (N/30 days)"
when < 30.

**UI hook:** `OverviewTab → ChartsGrid → "Buzz volume × 30d"` panel — the
threshold legend is already in the UI; baseline-quality flag is missing.

## Gap 7 — Engagement-weighted tweet metadata

**Why:** Design doc Stage 2 (NLP Classification) calls for `public_metrics`
(likes, retweets, replies, quotes) per tweet, plus a derived `controversial`
flag (`replies / likes > 0.3`). These shape the per-evidence-item engagement
column and the bull/bear weighting.

**Shape needed:** Embedded within Gap 3's evidence-item endpoint — the
`engagement` block.

**UI hook:** Reserved row in Evidence chat-style cards (today shows source
badges + sample stats only).

## Gap 8 — Velocity-trigger threshold + alert payload

**Why:** Design doc says Social Velocity "is not charted separately" — it
fires alerts when the threshold crosses. The Insights tab today shows buzz
spikes from `useRsSpikes()`; it should also show velocity crossovers.

**Shape needed:** `GET /api/departments/retail_sentiment/alerts` returning
all currently-active triggers across velocity, divergence, momentum-crossover,
and buzz-spike — not just buzz spikes. Each alert needs `kind`, `ticker`,
`triggered_at`, `value`, `threshold`, `direction`.

**UI hook:** `InsightsTab → "Active signals"` already iterates `spikes[]` —
extend to a unified `alerts[]` once endpoint exists.

---

## Out of scope (explicitly deferred)

- **5th tab "Data architecture"** from sentiment_dashboard_design.md —
  product decision: pipeline docs live in `planning/`, not in the UI.
- **Word cloud / treemap** — requires Gap 5 (narrative themes); will be added
  in a Narrative tracker iteration.
- **Backtesting module** — separate feature.
- **Taiwan market coverage / Chinese-language NLP** — separate feature.
- **Slack / email / Telegram alert delivery** — separate feature; Gap 8
  unblocks the data side only.
