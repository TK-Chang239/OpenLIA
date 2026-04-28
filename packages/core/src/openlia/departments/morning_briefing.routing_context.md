# Morning Briefing — Routing Context

## What this department does

Morning Briefing produces the daily multi-section briefing a buy-side
PM expects on their desk before the open. It surveys overnight news,
upcoming economic releases, the user's watchlist, and macro context;
it stitches all of that into a deterministic, sectioned report
(market wrap, watchlist movers, economic calendar, headlines, etc.).
In chat mode it answers narrow follow-ups on the most recent briefing
or a specific section. It is breadth-first across many tickers and
topics, where Equity Research is depth-first on one name.

## Data this department needs access to

The router should authorize broad market-coverage tools:

- Multi-ticker quote sweeps (watchlist + major indices + a handful
  of macro proxies like UUP, TIP, HYG, LQD).
- Recent historical prices for short-window change calculations.
- General-purpose company news, with the ability to filter by
  watchlist.
- Economic-calendar lookups for the day's releases and central-bank
  events.
- Macro indicator pulls (CPI, PMI, GDP YoY) for any "what changed
  overnight" callouts.
- Web search as a fallback for cross-asset context (oil, FX, BTC) the
  configured connectors don't cover.

## Out-of-scope topics

- Single-name deep dives or fundamentals walks
  (route to Equity Research).
- Earnings-print scorecards (route to Earnings Update).
- Macro regime narrative (Four Seasons / Debt Cycle / World Order)
  (route to Macro Research).
- Real-time retail-sentiment dashboards (route to Retail Sentiment).
- Crash-probability dashboards (route to Panic Thermometer).

## Example prompts and the data they imply

1. **"Generate today's morning briefing."** — full breadth pull:
   watchlist quotes, major-index quotes, overnight headlines,
   today's economic calendar, optional macro indicator deltas.
2. **"What's on the economic calendar today?"** — economic-calendar
   tool only.
3. **"Anything overnight on my watchlist I should know about?"** —
   watchlist quotes + filtered company-news with an overnight time
   window.
4. **"How did Asia close?"** — quote sweep across regional index
   ETFs (e.g., EWJ, FXI, EEM); web search if no Asia-index ETF
   coverage is configured.
5. **"What happened with oil overnight?"** — quote on USO/BNO plus
   recent commodity-relevant headlines; web search fallback.
6. **"Summarize the Fed news this morning."** — recent news filtered
   to "Federal Reserve" plus the day's economic calendar entries.
