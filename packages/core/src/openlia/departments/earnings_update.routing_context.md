# Earnings Update — Routing Context

## What this department does

Earnings Update is the post-print analyst. For a single ticker
(or a small list) it produces a scorecard-focused report immediately
after a quarterly earnings release: beat/miss on headline metrics,
guidance changes, segment performance, management commentary,
analyst reaction, and a thesis-check verdict. In chat mode it
answers narrow questions about a recent print or the upcoming
earnings calendar. It is short-cycle and event-driven; it does not
do long-form initiation work.

## Data this department needs access to

The router should bias toward earnings-cycle tools:

- Earnings calendar (next-print date, time of day, fiscal period).
- Earnings history with consensus estimates (revenue and EPS),
  reported numbers, surprise %, and guidance text.
- Earnings-call transcripts when the connector exposes them.
- Income statement and cash-flow statement, quarterly granularity.
- Real-time and recent quote history (immediate post-print reaction).
- Analyst rating changes and price-target revisions in the days
  bracketing the print.
- Company news with a recent date filter — the post-earnings hot
  takes and downstream coverage.

## Out-of-scope topics

- Initiating coverage on a name from scratch (route to Equity Research).
- Multi-quarter trend analysis without an earnings event in scope
  (route to Equity Research).
- Daily multi-name briefings (route to Morning Briefing).
- Macro regime or sector-rotation calls (route to Macro Research).
- Retail-sentiment dashboards on the same ticker (route to
  Retail Sentiment).

## Example prompts and the data they imply

1. **"Run an earnings update on NVDA for the quarter that just printed."**
   — earnings history (latest row), transcript if available, income
   statement (current quarter vs. prior quarter and YoY), guidance
   commentary, post-print quote action, analyst reactions.
2. **"Did Costco beat or miss this morning?"** — earnings-calendar
   lookup + earnings-history latest row. A short answer; no full
   report needed.
3. **"Summarize MSFT's last earnings call commentary on AI."** —
   transcripts tool (filtered to the AI section), no financials
   needed.
4. **"Who reports next week that I should pay attention to in semis?"**
   — earnings calendar with a sector filter; minimal financials.
5. **"What did analysts change on AMZN after the Q3 print?"** —
   analyst-rating-changes tool with a date filter; ignore the
   statements.
6. **"How big was the surprise vs. consensus at TSLA last quarter?"**
   — earnings-history surprise % only; one row of the earnings table.
