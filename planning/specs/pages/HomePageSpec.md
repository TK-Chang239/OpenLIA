# Home Page Spec

> **Status:** SHIPPED. This spec documents the shipped Home page.
>
> **Grounded in shipped code:** `frontend/src/pages/Home.tsx` and `frontend/src/pages/home/*` (`MorningBriefingSnapshotCard`, `TickerStrip`, `PortfolioGlanceCard`, `SuggestedGrid`, `RecentStrip`, plus `greetings.ts`, `dateStamp.ts`, `suggestionsBank.ts`).

## Page Overview

Home is the landing page: a personalized greeting followed by five stacked "glance" blocks that surface the user's most relevant live state and quick entry points into the departments. Every block is best-effort and self-hides or shows an empty/connect hint when its data is unavailable, so the page never renders broken tiles.

The page is a centered single column (`max-w-[760px]`), with a staggered fade-up entrance per block. It refreshes the date stamp once a minute so a long-open tab does not show a stale day after midnight.

## Page Functionalities

The greeting header shows a date stamp (`formatDateStamp`), a time-of-day greeting with the user's first name, and a rotating accented headline (`pickGreeting` over a bilingual greeting bank seeded by the local day). Below it, five blocks render in order:

1. **Morning-Briefing snapshot** (`MorningBriefingSnapshotCard`) — the latest completed Morning Briefing run (`listMbRuns("completed")`, newest first). Shows the edition date, a "LIA" mark, the briefing subject, an optional rating, "Today's read" lede (cover subtitle), up to 4 cover metrics with tone-colored change values, and links: **Open briefing** (`/morning-briefing`) and **Ask LIA to brief** (`/secretary?prompt=…`). Because the engine emits prose sections + a cover summary, the card surfaces that summary rather than fabricating macro/watchlist/calendar columns. Empty state prompts to open the briefing; a loading state shows while fetching.
2. **Ticker strip** (`TickerStrip`) — a row of live market indices (`fetchMarketIndices`, polled every 60s). Each cell shows label, value, and a signed daily % change (green/red). Three distinct states: live quotes → the strip; server reports **no EODHD key** (`available === false`) → a single "connect EODHD" hint cell (the route's documented purpose); empty/transient error → the strip is hidden entirely.
3. **Portfolio glance** (`PortfolioGlanceCard`) — total NAV (in the display currency), an optional "today" day-P/L chip, a time-window tab row (1D / 1M / 3M / 1Y / ALL) driving a live value-series area chart (`fetchValueSeries`), a positions count, a period-return chip, and an **Open portfolio** link (`/portfolio`). Value is `—` while loading; an empty portfolio shows a "portfolio empty" affordance. Mixed-currency portfolios (null combined total) are guarded — the day-P/L is suppressed when FX is unavailable.
4. **Suggested grid** (`SuggestedGrid`) — a 2-column grid of daily-seeded prompt suggestions (`pickSuggestions` over `SUGGESTION_BANK`, seeded by local day + a refresh salt). Each card shows a live/idle dot, a tag, the question, and a department source hint with an icon. Clicking a card opens the Secretary pre-loaded with the prompt (`/secretary?prompt=…`). A "Refresh" control reshuffles the picks. **Demo mode** (`VITE_DEMO_MODE`) relabels the header "Suggested prompts" and makes the cards display-only (no navigation).
5. **Recent strip** (`RecentStrip`) — up to 5 most-recent chat sessions (`listSessions`, newest first) as pills that deep-link to the department where each chat lives (path resolved from the shared sidebar nav table), with a compact relative-time token ("now" / "5m" / "3h" / "2d"). The strip hides entirely when there are no sessions.

## Page Design

### Layout

- Container: `mx-auto w-full max-w-[760px] px-8 pt-10 pb-16`, vertical flex, `gap-7`.
- Greeting: date-stamp eyebrow (mono, uppercase) + a large display headline (`text-[52px]`) "{time-of-day}, {name}." followed by the rotating phrase with a serif-italic accent word.
- Blocks: each wrapped in a `Block` that fades/translates up on mount with a per-index delay (stagger `0.06`).

### Block visual notes

| Block | Container |
|---|---|
| Morning briefing | Rounded card, header row (mark + subject + edition/rating + Open link), lede row, metric row, footer with Ask-LIA link. |
| Ticker strip | Bordered pill-row of index cells with per-cell dividers. |
| Portfolio glance | Rounded card: NAV headline + day chip, tab row, SVG area chart with gridlines, footer (positions · period return · Open link). |
| Suggested grid | Section header (title + Refresh) + responsive 2-col card grid. |
| Recent strip | Top-bordered row: "Recent" label + wrapped session pills. |

## States

| State | Description |
|---|---|
| **Fresh / no data** | Greeting always renders; each block independently shows its loading/empty/connect/hidden variant. Ticker strip and Recent strip may render nothing. |
| **Populated** | Live briefing snapshot, index strip, portfolio chart, suggestions, and recent pills. |
| **Demo mode** | Suggested grid is display-only and relabeled; other blocks behave normally against demo fixtures. |

## Configurations

- **LLM:** none directly. Home reads other departments' outputs (Morning Briefing runs, chat sessions) and market/portfolio data for display; it does not invoke an LLM itself.
- **Data:** market indices + portfolio value series require an EODHD key; both degrade gracefully (connect hint / `—`) when absent.

## Notes / Backlog

Per `dev-backlog/home.md`, several enrichments (a dedicated MB snapshot API, personalized suggestions, richer recent pills, a topbar status row) are deferred; the shipped blocks above use existing department/market APIs.
