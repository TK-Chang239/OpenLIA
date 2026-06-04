# Retail Sentiment — Routing Context

## What this department does

Retail Sentiment is a web-search-backbone dashboard department. It surfaces
the retail investing community's collective view on a single ticker by
searching the open web — Reddit threads, StockTwits posts, financial Twitter,
earnings-call summaries, and news commentary — rather than relying on a
proprietary social-data connector. The engine (report_dash_rs) gathers
discussion fragments via web search, synthesizes a sentiment read across
multiple retail forums and commentary sources, and produces a structured
snapshot: overall sentiment direction (bullish / bearish / mixed), buzz
volume estimate, notable narratives driving the conversation, contrarian
signals worth monitoring, and an optional 2-4 sentence plain-English summary.
Financial and news connectors are optional enrichment: if a validated
FINANCIAL connector is present the engine can anchor the sentiment read to
live price and volume; a NEWS connector supplies headline context for
cross-source agreement scoring. Neither is required for the dashboard to run.

## Data this department needs access to

RS's primary data source is the web search connector (required). The engine
issues targeted queries — e.g. "NVDA retail sentiment Reddit today" or
"$TSLA StockTwits discussion" — and synthesizes the retrieved content
directly. The router should authorize:

- Web search queries covering retail discussion forums, social-finance
  platforms, and financial news commentary for the requested ticker.
- Optional real-time and recent price quotes if a FINANCIAL connector is
  validated; used to anchor sentiment reads to price action and identify
  buzz-price divergences.
- Optional company news headlines if a NEWS connector is validated; used
  to distinguish retail-driven narratives from news-driven ones and score
  cross-source agreement between professional and retail views.

No per-post classification pipeline, no batch LLM call over raw social
posts, and no connector-resident `social_posts` endpoint is required.
The EODHD connector's `social_posts` runner_spec declaration is retained
as connector-resolution metadata (a stable public API) but is not
activated by this engine.

## Out-of-scope topics

- Fundamentals analysis or single-name coverage reports
  (route to Equity Research).
- Earnings-print scorecards (route to Earnings Update).
- Macro regime calls (route to Macro Research).
- Daily generic morning briefings (route to Morning Briefing).
- Crash-probability dashboards (route to Panic Thermometer).

## Example prompts and the data they imply

1. **"What's retail saying about NVDA right now?"** — web search for
   recent retail discussion on NVDA; synthesize sentiment direction, buzz
   volume, and dominant narratives from forum threads and commentary.
2. **"Has there been a buzz spike on GME this week?"** — web search for
   recent GME discussion volume across retail platforms; identify whether
   activity is elevated relative to a baseline read.
3. **"Compare retail sentiment on AAPL versus MSFT."** — two parallel
   web-search passes, one per ticker; side-by-side sentiment direction
   and narrative summary for each.
4. **"Why is retail so bearish on TSLA lately?"** — web search for
   bearish retail narratives on TSLA; surface the specific concerns or
   catalysts driving the negative read.
5. **"Summarize today's retail picture on PLTR in plain English."**
   — web search for current retail discussion on PLTR; produce a 2-4
   sentence plain-English summary with sentiment direction and top
   narrative themes.
6. **"Are retail investors and the news in agreement on SPCE?"** —
   web search for retail commentary plus NEWS connector headlines if
   available; compare the retail narrative to professional coverage and
   flag agreement or divergence.
