# Earnings Update (v2) Page Spec

> **Status:** SHIPPED. This spec documents the shipped Earnings Update v2 surface, folding in the design doc `planning/2026-05-29-earnings-update-v2-frontend-design.md`.
>
> **Grounded in shipped code:** `frontend/src/pages/departments/EarningsUpdate.tsx`, `frontend/src/components/earnings-update/*` (feed, calendar, coverage drawer, cabinet, modals), `frontend/src/hooks/useEu*.ts`, `frontend/src/api/earnings-update.ts`, and `frontend/src/components/sidebar/{Sidebar,NavItem}.tsx` (department dot).

## Page Overview

Earnings Update (EU) tracks a **watchlist** of tickers and produces a structured earnings-update report around each name's earnings release. Reports fire automatically when a tracked ticker reports (scheduled from the EODHD earnings calendar) and can also be run on demand. EU keeps the earlier v2/v1 visual design; the v2 rewire changed the controls and data wiring (user-chosen model, DB-backed templates, per-user connector toggles, automatic release triggering, structured reports) per the design doc § *Strategy*.

The page is a **feed surface** (no chat interface): a hero stat band, a stream/calendar toggle, dated feed sections, and a set of drawers/modals for watchlist coverage, on-demand runs, the full report cabinet, and settings.

The engine is a fork of the v3 single-model engine (`report_eu`). When the server has the engine disabled, the page shows a disabled banner.

## Page Functionalities

1. **Hero stat band** (`EuHero`) — reports this week, tracked tickers, and upcoming-this-week counts, derived from the runs list and schedule. A watchlist-empty variant nudges the user to add coverage.
2. **Live pill** (header) — when one or more runs are generating (`liveCount`), a pulsing "Live" pill appears in the header.
3. **Refresh earnings dates** (`EuRefreshButton`) — calls `syncWatchlist()` to re-pull the earnings calendar for tracked tickers, then refreshes the watchlist and schedule. Disabled when the watchlist is empty.
4. **Watchlist / Coverage drawer** (`CoverageDrawer`) — opened from the header "Watchlist" button (shows the tracked count). Add/remove tickers, see each ticker's next scheduled earnings (joined via the schedule `byTicker` map) and its recent reports; open a report from a row.
5. **Generate report (on-demand modal)** (`OnDemandReportModal`) — opened from the header "Generate report" button. Pick a watchlist ticker (or an ad-hoc one) and start a run; on start the page shows a live card and streams progress via `useEuRunStream`.
6. **Settings modal** (`ReportSettingsModal`) — opened from the header "Settings" button. Report template/length/model and the three per-user **connector toggles** (financial data, earnings calendar, web search) per the design doc § 4.
7. **Stream / Calendar view toggle** (`EuViewToggle`) — switches the body between the dated feed stream and a read-only upcoming-earnings **calendar** (`EuCalendar`, built from `GET /schedule` + runs).
8. **Feed stream** — dated sections built by `feedHelpers` (`groupReports`/`searchReports`):
   - **Today** — a hero `EuBigCard` (or the live generating/completed card), then the rest as `EuReportRow`s.
   - **Up next (24h)** — pending scheduled earnings as `EuUpNextCard`s.
   - **Earlier this week** — completed reports as rows.
   A search box filters the stream client-side.
9. **Live run card** — while a run streams, `EuGeneratingCard` shows progress (sections written, tools in flight) with cancel; on completion it swaps to a completed `EuBigCard` and refreshes the runs list. Cancelled/failed runs dismiss the live card and refresh so any partial report surfaces.
10. **Open report** — any card/row opens the rendered report in the `FileViewer` (source `{kind: "eu_v2_report", reportId}`), with an inline delete action.
11. **EU Cabinet** (`EUCabinetView`) — a "View all reports" full-list view of every run, with open + remove.
12. **Remove report** — a `ConfirmDialog` guards deletion (`deleteRun`), then refreshes the feed; removing the live run also clears the live card.
13. **Sidebar department dot** — the nav item for Earnings Update shows the standard unread notification dot (`NavItem` `hasUnread`, driven by `useNotificationPoll`'s `unreadByDepartment`). A completed scheduled/on-demand report raises an unread notification; visiting the page marks it read.

## Page Design

### Header (52px)

Title "Earnings Update" · optional Live pill · **Refresh dates** (`EuRefreshButton`) · **Watchlist** button (with count) · **Generate report** (accent primary) · **Settings** button.

### Body

`max-w-[1200px]` centered column. Order: disabled banner (if engine off) → error banner (retry) → hero stat band → view toggle + search → **calendar** or **stream sections** → "View all reports" link into the Cabinet. Feed sections animate in with a staggered fade-up.

### Drawers / modals

- `CoverageDrawer` — watchlist coverage (add/remove/open).
- `OnDemandReportModal` — start an ad-hoc run.
- `EUCabinetView` — full report list (mounted when opened).
- `ReportSettingsModal` — report + connector settings (mounted only when settings exist).
- `ConfirmDialog` — remove-report confirmation.

## States

| State | Description |
|---|---|
| **Loading** | Skeletons for the hero + feed while watchlist/runs load. |
| **All empty** | No watchlist entries, no runs, no live card → empty hero + `EuEmptyPage` prompting to open the watchlist. |
| **Populated** | Hero stats + feed stream (or calendar). |
| **Live** | A generating card in Today; header Live pill; `useEuRunStream` drives progress. |
| **Disabled** | Engine off on the server → `eu-v2-disabled-banner`. |
| **Error** | Watchlist/runs load failure → error banner with Retry. |

## Report Framework

EU generates one structured earnings-update report per run (HTML/PDF/DOCX), rendered in the `FileViewer`. Triggered by (a) the earnings-calendar scheduler when a tracked ticker reports, or (b) the on-demand modal. Report shape is driven by the DB-backed template + settings.

## Configurations

- **LLM:** user-chosen model in the Settings modal (per design doc § 4).
- **Connectors:** three per-user toggles — financial data, earnings calendar, web search — passed to the engine.
- **Data:** EODHD earnings calendar drives scheduling (`syncWatchlist`); financial data + web search enrich the report per the connector toggles.

## Out of Scope / Notes

- No chat interface (feed surface only).
- The forward "Up Next" section and calendar are **read-only** upcoming-earnings views (the v1 cron builder was removed per design doc § 2).
- See `planning/2026-05-29-earnings-update-v2-frontend-design.md` § *As-built notes* for divergences recorded during implementation.
