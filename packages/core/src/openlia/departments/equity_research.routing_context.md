# Equity Research — Routing Context

## What this department does

Equity Research is OpenLIA's bottoms-up, single-name analyst. It
produces multi-section reports on individual companies (initiation,
update, sector survey) and answers in-chat follow-ups on the same.
Its outputs are fundamentals-driven: revenue and margin trends,
balance-sheet composition, valuation versus peers and history,
catalysts, and bear-case analysis. It does not handle portfolio-level
allocation questions and does not handle macro regime calls.

## Data this department needs access to

Equity Research is connector-heavy and the router should freely
authorize fundamentals-grade tools:

- Real-time and historical quotes; multi-year price history for
  charting and ratio bases.
- Income statement, balance sheet, and cash-flow statement, both
  annual and quarterly, ideally with at least 5y of history.
- Company profile (sector, GICS, market cap, share count, headquarters).
- Analyst ratings, price targets, and rating-change history.
- Insider transactions and 13F-style institutional-holdings snapshots.
- Earnings history (beats/misses, surprise %, guidance text).
- Company-level and sector news; web search for context not in the
  news connectors (e.g., a specific S-1 disclosure quote).
- Social-sentiment lookups when the user explicitly asks how retail is
  positioned on the name (otherwise prefer Retail Sentiment).

## Out-of-scope topics

- Daily multi-name briefings (route to Morning Briefing).
- Earnings-day scorecards and post-print walkthroughs
  (route to Earnings Update).
- Macro regime, debt-cycle, or seasonality questions
  (route to Macro Research).
- Real-time retail-sentiment dashboards (route to Retail Sentiment).
- Crash-probability or panic dashboards (route to Panic Thermometer).
- Portfolio-level allocation, rebalancing, or risk-budget questions
  (these belong to the Portfolio surface, not a department).

## Example prompts and the data they imply

1. **"Initiate coverage on NVDA."** — full fundamentals pull
   (5y financials, peer comps, analyst ratings, recent news) and a
   multi-section initiation report. The router should authorize the
   widest tool set this dept has.
2. **"What changed at AAPL since their last quarter?"** — recent news,
   latest filings, latest earnings, price action vs. a 3-month window,
   any analyst rating changes since print.
3. **"How does CRM's gross margin compare to ADBE and MSFT?"** —
   income statements (gross profit, revenue) for three names; no
   news tools required.
4. **"What's the bear case on Palantir?"** — financial statements,
   short-interest if available, analyst downgrades, recent
   negative news, web search for skeptical commentary.
5. **"Walk me through the semis sector right now."** — sector-survey
   mode: peer-list lookup, valuation table, news summary across the
   group, and any single-name standouts.
6. **"How much insider selling has there been at TSLA in 2025?"** —
   insider-transactions tool only; possibly a stock-price overlay.
