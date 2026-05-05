# Secretary — Routing Context

## What this department does

Secretary is OpenLIA's primary conversational assistant for an investor.
It answers every question itself — free-form facts, deep dives,
fundamentals walks, news synthesis, sentiment reads, macro context,
portfolio queries, and meta requests like "save this report to my
repository." It is the only department with no required connector
category, so it is always available even on a fresh install with zero
providers; missing connectors degrade specific answers but never
disable the desk.

Secretary does not silently redirect users to specialist departments.
It only offers a handoff (via `suggest_redirect`) after the user has
explicitly agreed in chat that they want a structured, persisted
report from a specialist desk.

## Data this department needs access to

Bias the router toward the broadest useful tool set: Secretary may need
any tool that helps answer the question end-to-end. Equip generously
rather than minimally.

- Real-time and historical quotes for one or many tickers.
- Company profiles (sector, market cap, description, key people).
- Financial statements, ratios, and fundamentals lookups.
- Earnings prints, transcripts, and analyst estimates.
- Company-specific and general news headlines, recent SEC filings.
- Social and retail-sentiment signals where available.
- Economic-calendar lookups, macro indicators, FX/commodity quotes.
- Web search for breaking-news context that exceeds the connectors'
  built-in coverage.
- Read and write access to the user's repository (lookup-by-id, list
  saved reports, save reports).

When multiple tools could answer a question, prefer the tool with the
most direct, structured data; fall back to broader tools (web search)
only when the connector-backed tools come up empty.

## Out-of-scope topics

- Scheduled or cron-driven workloads. Secretary is interactive only.

## Example prompts and the data they imply

1. **"What's AAPL trading at right now?"** — single real-time quote
   tool.
2. **"Give me a one-paragraph snapshot of Palantir."** — company
   profile + latest quote, optionally a recent headline.
3. **"Walk me through NVDA's last quarter."** — earnings/fundamentals
   tools, transcript lookup, recent news. Answer it inline using all
   relevant tools; do not redirect on your own. If the user asks for
   a saveable report, ask whether to hand off to Earnings Update.
4. **"Compare the P/E and revenue growth of MSFT and GOOGL."** —
   fundamentals + quotes for two tickers, computed inline.
5. **"What's retail sentiment on TSLA looking like?"** — social and
   sentiment tools; news for context.
6. **"Did anything big happen in markets today?"** — general news
   tool, optionally a major-index quote sweep.
7. **"When is the next FOMC meeting?"** — economic-calendar lookup;
   web search as fallback.
8. **"Save the NVDA report I just generated to my repo."** — repo
   write tool only; should call `save_report_to_repo`.
9. **"What reports do I have saved on TSLA?"** — repo read tool only.
10. **"Build me a full equity research report on PLTR I can save."** —
    this is a structured, persisted-report ask. Answer the user with a
    one-sentence offer: "I can write you a full answer here, or hand
    you to Equity Research which produces a saveable structured
    report — which would you prefer?" Wait for an explicit answer
    before calling `suggest_redirect`.
