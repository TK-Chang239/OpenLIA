# Panic Thermometer — Routing Context

## What this department does

Panic Thermometer is a dashboard-only crash-risk department. It
maintains five panels — oil, inflation, fed-language, wage-growth,
and diplomacy — each one scored on a stress scale and aggregated into
an overall "panic" reading. Each panel is a deterministic mix of
macro indicators and a small, fixed news search for tone signals.
The department surfaces a single big-picture verdict ("calm",
"watchful", "alarmed") plus per-panel breakdowns. In chat mode it
answers narrow follow-ups on the most recent computation, anchored
in cached panel values rather than re-fetching.

## Data this department needs access to

The router should authorize compact stress-signal pulls:

- Historical price series and quotes for stress proxies: WTI/Brent
  (oil panel), gold and TIP (inflation panel), DXY (diplomacy panel).
- Macro indicators: headline + core CPI (inflation), nonfarm wages
  and ECI (wage-growth), policy-rate forecasts (fed-language).
- Economic-calendar reads for upcoming Fed events.
- Targeted news pulls for fed-language tone (FOMC statements,
  speeches) and diplomacy (geopolitical headlines).

## Out-of-scope topics

- Single-name analysis (route to Equity Research).
- Earnings prints (route to Earnings Update).
- Daily generic briefings (route to Morning Briefing).
- Long-horizon macro regime calls — Debt Cycle, Four Seasons, World
  Order (route to Macro Research).
- Retail-sentiment metrics on individual tickers (route to
  Retail Sentiment).

## Example prompts and the data they imply

1. **"What's the current panic reading?"** — read-only against the
   cached panel values; no fetch needed.
2. **"Refresh the oil panel."** — recent oil quote / WTI history
   plus a small set of energy-market headlines.
3. **"Why is the fed-language panel elevated?"** — surface the
   panel's underlying news pulls (recent FOMC commentary) and
   policy-rate-expectation series; rely on cached scoring.
4. **"How worried should I be about wage-growth right now?"** —
   wage / ECI macro indicators; no equities tooling needed.
5. **"What does the diplomacy panel see?"** — cached geopolitical
   headlines + DXY trend; rely on the panel's last computation.
6. **"Did the inflation panel just flip to alarmed?"** — recent
   panel-history rows; CPI release deltas. No deep news pull
   unless the user asks why.
