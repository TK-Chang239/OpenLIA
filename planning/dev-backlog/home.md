# Home Page — dev backlog

The Home page (`/`) was rebuilt against the OpenLIAv3 design at
`OpenLIAv3/app/index-empty.html` on 2026-05-06. Per Q1=A, every block ships
with placeholder data so the visual is pixel-faithful today; this file
tracks the wiring that still needs to land.

## Deferred items

### MORNING_BRIEFING_SNAPSHOT_API
The MB snapshot card on Home renders hardcoded data (edition #218, lede,
3 macro events, 3 watchlist entries, 3 calendar events, foot strip).

Needed: a `/api/departments/morning-briefing/today` (or similar) endpoint
that returns the latest MB run's summary in a snapshot shape:

```ts
interface MBSnapshot {
  edition_number: number;
  date_label: string;            // "TUE 02 MAY"
  status_label: string;          // "Pre-open · 2h 14m to bell"
  lede: { meta: string[]; html: string };
  macro: MacroEvent[];           // 3
  watchlist: WatchEntry[];       // ≤ 3
  calendar: CalendarEntry[];     // 3
  foot: { stats: string[]; updated_at: string };
}
```

The snapshot likely cherry-picks the highest-confidence sections from
the latest MB report. Wire the card once the endpoint exists.

File: `frontend/src/pages/home/MorningBriefingSnapshotCard.tsx`

### PORTFOLIO_NAV_TIMESERIES_API
The portfolio glance card renders synthetic SVG paths for all 4 tabs
(NAV / vs SPX / Drawdown / Exposure). NAV value, daily P&L, position
count, YTD %, Sharpe are all placeholder.

Needed: portfolio endpoints that return current NAV + a sparkline-ready
timeseries per tab. Until then the tabs only swap visual stubs; clicking
them is harmless but doesn't represent real positions.

File: `frontend/src/pages/home/PortfolioGlanceCard.tsx`

### TICKER_STRIP_LIVE_QUOTES
The 6-cell ticker strip (S&P FUT / NASDAQ / VIX / 10Y / DXY / BTC)
renders hardcoded values and deltas.

Needed: a low-frequency quote-feed (poll once a minute or SSE) that
covers index futures, vol, rates, FX, and BTC. FMP MCP can serve most
of these; need a server-side cache to avoid per-render API hits.

File: `frontend/src/pages/home/TickerStrip.tsx`

### LLM_SUGGESTIONS_PERSONALISED
The "Suggested · today" grid picks 4 cards from a static curated bank of
12 prompts, deterministically per local day. Refresh button shifts the
seed for an alternate selection within the same bank.

Future: replace the curated bank with prompts generated from the user's
recent activity, watchlist, and current market state. Likely a dedicated
LLM pipeline that runs at most a few times per session.

Files:
- `frontend/src/pages/home/suggestionsBank.ts` (bank + picker)
- `frontend/src/pages/home/SuggestedGrid.tsx`

### RECENT_PILLS_LIVE_DATA
The Recent strip renders 5 hardcoded titles + relative-time labels and
is currently inert (cursor:default).

Needed: pull the user's 5 most recent items — strongest signal is
probably saved repo items + last-touched chat sessions, merged and
deduped. Each pill should route to the relevant artifact:
- chat session → `/secretary?session_id=…` (pass through to existing
  ChatHeaderRegistry select flow)
- repo item    → open the FileViewer with that artifact

File: `frontend/src/pages/home/RecentStrip.tsx`

### TOPBAR_STATUS_ROW
Per Q2 the design's topbar status row (`LIVE_FEED_ACTIVE` pill,
`TUE · 08:14 UTC` stamp, `CONGRESS_ACTIVE: 119` stamp) was deferred
**globally** — not on Home, not on Secretary, not anywhere. The
elements need real signals to render honestly:
- LIVE_FEED_ACTIVE: gated on a global market-data feed health check.
- Time stamp: live local time, updated each minute (cheap once we add
  it to TopBar).
- CONGRESS_ACTIVE: gated on the senate/congress trade tracker pipeline.

When the underlying signals exist, surface them in the global `TopBar`
component (`frontend/src/components/topbar/TopBar.tsx`) so the row is
visible on every page rather than re-implemented per-route.

### GREETING_BANK_PERSONALITY
Greeting bank lives at `frontend/src/pages/home/greetings.ts`. Picker is
deterministic per local day; user sees one phrase that rotates at
midnight. Bank can grow over time — the picker uses `% bank.length` so
adding entries is safe.

## Honored design decisions (closed)

| Q | Answer | Closed by |
|---|---|---|
| Q1 — wiring scope | Pixel-match with placeholders | This commit |
| Q2 — topbar status row | Skip everywhere globally | This commit |
| Q3 — block coverage | All 5 blocks ship | This commit |
| Q4(a) — hero hairline | Drop session counter; live date stamp `TUE · 06 MAY 2026` | This commit |
| Q4(b) — accent word | Curated rotation, deterministic per day | This commit |
| Q5 — affordances | Routes + prompt prefill (no auto-send); tabs visual; recent inert | This commit |
| Q5 followup — suggestions | Curated bank, day-seeded picker, refresh shuffles | This commit |
