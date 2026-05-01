# Secretary — Routing Context

## What this department does

Secretary is OpenLIA's general-purpose conversational front desk for an
investor. It answers free-form factual questions about markets,
companies, and the user's own portfolio; handles meta requests
("save this report to my repository", "what reports do I have on
NVDA?"); and triages users toward specialist departments when their
ask actually warrants a full report, dashboard, or scheduled job.
It is the only department with no required connector category — it is
always available even on a fresh install with zero providers.

## Data this department needs access to

Secretary biases the router toward tools that surface compact,
single-shot facts:

- Real-time and historical quotes for a single ticker.
- Company profile lookups (sector, market cap, brief description).
- General company news headlines and recent filings.
- Light economic-calendar lookups for upcoming events.
- Web search for breaking-news context that exceeds the connectors'
  built-in news coverage.
- Read-only access to the user's repository (lookup-by-id, list saved
  reports).

When connectors expose richer endpoints (sentiment, options, screeners),
Secretary should still prefer the simplest tool that answers the
question — full deep-dive data belongs in a specialist dept.

## Out-of-scope topics

- Producing a multi-section equity research report (route to
  Equity Research).
- Post-earnings scorecard analysis (route to Earnings Update).
- Daily morning-briefing generation (route to Morning Briefing).
- Macro-regime dashboards or framework scoring (route to Macro Research).
- Retail-sentiment metric snapshots (route to Retail Sentiment).
- Scheduled / cron-driven workloads of any kind.

For these, Secretary should use the `suggest_redirect` extra-tool
rather than attempting the work inline.

## Example prompts and the data they imply

1. **"What's AAPL trading at right now?"** — single real-time quote
   tool. No news, no profile lookup needed.
2. **"Give me a one-paragraph snapshot of Palantir."** — company
   profile + latest quote. Optional: one or two recent headlines.
3. **"Did anything big happen in markets today?"** — general news
   tool, optionally a major-index quote sweep. No company-specific
   tooling.
4. **"Save the NVDA report I just generated to my repo."** — repo
   write tool only; no market data needed. Should call
   `save_report_to_repo`.
5. **"What reports do I have saved on TSLA?"** — repo read tool only.
6. **"When is the next FOMC meeting?"** — economic-calendar lookup.
   Web search acceptable as a fallback if no calendar connector is
   configured.
7. **"Compare the P/E of MSFT and GOOGL."** — quote + profile (or
   light fundamentals) for two tickers. If a deeper valuation walk is
   asked, suggest redirecting to Equity Research.
