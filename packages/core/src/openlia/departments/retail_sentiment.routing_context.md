# Retail Sentiment — Routing Context

## What this department does

Retail Sentiment is a deterministic-runner dashboard department. It
ingests social posts and news mentions for a single ticker, classifies
each one (bullish / bearish / neutral) via a batch LLM call, and
computes a 12-metric snapshot — sentiment score, buzz volume, momentum,
bull/bear ratio, buzz-sentiment divergence, cross-source agreement,
plus five optional metrics (options skew, short interest, etc.). It
also detects 7-day buzz spikes and emits an optional 2-4 sentence
narrative summary. In chat mode it answers narrow questions about a
freshly-computed snapshot or alert, citing the metric values rather
than re-fetching posts.

## Data this department needs access to

RS pulls its primary input — `social_posts` — through the financial
connectors' sentiment endpoints (EODHD, FMP), not through a separate
social provider. The router should authorize:

- Sentiment-endpoint reads on financial connectors (the `social_posts`
  need): post id, ticker, source, text, engagement counters,
  created-at timestamp.
- Real-time and recent quotes for the ticker so metric snapshots can
  be price-anchored.
- Company news for cross-source agreement scoring (a financial-news
  feed and a retail-platform feed should agree or disagree).
- Optional inputs for the five extended metrics: historical price
  series (volatility), options chains, short interest, institutional
  holdings.

## Out-of-scope topics

- Fundamentals analysis or single-name coverage reports
  (route to Equity Research).
- Earnings-print scorecards (route to Earnings Update).
- Macro regime calls (route to Macro Research).
- Daily generic morning briefings (route to Morning Briefing).
- Crash-probability dashboards (route to Panic Thermometer).

## Example prompts and the data they imply

1. **"What's retail saying about NVDA right now?"** — `social_posts`
   need bound to `ticker=NVDA`, batch classification, full 12-metric
   snapshot.
2. **"Has there been a buzz spike on GME this week?"** — recent
   metric snapshots only; spike-detector run; no fresh posts needed
   if a recent snapshot exists.
3. **"Compare retail sentiment on AAPL versus MSFT."** — two parallel
   snapshots, comparison on sentiment score and bull/bear ratio.
4. **"Why is the buzz-sentiment divergence high on TSLA?"** —
   read-only against the cached snapshot; surface the underlying
   metric values plus any active signals.
5. **"Summarize today's retail picture on PLTR in plain English."**
   — snapshot + signals + the narrative-synthesis prompt for a
   2-4 sentence summary.
6. **"Are short-interest and retail sentiment diverging on SPCE?"** —
   short-interest optional input + sentiment score; relies on the
   extended metrics being available.
