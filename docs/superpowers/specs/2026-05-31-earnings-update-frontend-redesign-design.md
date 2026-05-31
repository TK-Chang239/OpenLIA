# Earnings Update — Frontend Redesign (mockup-aligned + Calendar) — Design

**Date:** 2026-05-31
**Branch:** `feat/eu-frontend-redesign` (off `origin/main` @ PR #214)
**Status:** Design approved; ready for implementation plan.
**Reference mockup:** `Earnings Update (standalone).html` (a static, vanilla-JS bundle the user supplied).

## Goal

Restyle the Earnings Update v2 page to the supplied standalone mockup's aesthetic, add a
Stream/Calendar view toggle with a working month-grid calendar, and strip all fabricated
financial data. **No backend changes** — the page adapts to the EU v2 HTTP contract that
already exists.

## Why this is a redesign, not a rebuild

The mockup was authored from the app's own design system (`tokens.css`: accent `#D4FF00`,
`IBM Plex Mono`, `Geist`, the same radii/motion tokens). The aesthetic therefore drops in
cleanly. The page already has a modular feed under
`frontend/src/components/earnings-update/feed/` (8 files) plus seven `useEu*` hooks and a
shared report renderer. We restyle those in place and add new calendar + view-toggle units,
rather than building a parallel component set.

## Locked scope decisions (from brainstorming Q&A)

1. **Drop all mock/fabricated metrics.** The backend stores none of: beats/misses counts,
   revenue/EPS *surprise* %, after-hours price move, "signal score", price sparklines, or the
   hero's beats/avg-surprise/avg-latency tiles. All are removed.
2. **Schedule estimates are real and kept.** `eps_estimate`, `revenue_estimate`, and
   `release_timing` exist on `EuScheduleEntry`. Up-next cards and calendar day-popovers keep
   their "Est. EPS / Est. Rev / Pre-market·After-close" lines, populated from these real
   fields. "Drop mock metrics" applies to *reported-row* verdict/surprise columns and the
   *hero financial* tiles — not to schedule estimates.
3. **Keep the existing `WatchlistModal`.** No slide-in coverage panel, no hardcoded
   suggestions list.
4. **On-demand run = dedicated topbar "Generate report" button**, reusing the existing
   `OnDemandReportModal` (free-text ticker → `POST /runs/start`).
5. **Keep a lightweight client-side feed search** (filters the Stream feed by ticker/subject).
6. **Remove the segmented filter** (All/Watchlist/Portfolio/Beats/Misses).
7. **Keep the 3 real hero tiles:** Reports this week, Tracked tickers, Upcoming this week.
8. **Calendar scope is watchlist-only** (accepted): the backend only knows the user's watched
   and run tickers, so the calendar shows those — not a market-wide calendar like the mockup's
   seed data. A small caption states this.

## Backend contract this consumes (existing, unchanged)

Base: `/api/departments/earnings-update/v2`. Relevant shapes:

- `GET /runs` → `RunSummary[]`: `{report_id, ticker, subject, template_id, trigger_kind,
  fiscal_date, language, length, status, created_at, completed_at, reasoning_effort}`.
  `status ∈ {running, completed, failed, cancelled}`. **No verdict/surprise/EPS/price fields.**
- `GET /schedule` → `{schedule: EuScheduleEntry[]}` where each is `{id, ticker, fiscal_date,
  release_timing, eps_estimate, revenue_estimate, scheduled_run_at, status, attempts,
  report_id}`. `release_timing ∈ {bmo, amc, pre_market, post_market, after_hours, null}`.
  **Returns only `status == "pending"` (future) entries.**
- `GET /watchlist` → `{entries: WatchlistEntry[]}`: `{id, ticker, company_name, created_at}`.
- `GET /runs/{id}` → `RunDetail` (sections/charts/citations/cover) — used only by the existing
  report renderer, not the feed.
- `GET /runs/{id}/events` — SSE live progress (existing `useEuRunStream`).
- `POST /runs/start` `{ticker}` → `{report_id}`.
- Settings / data-sources / templates / instructions — consumed only by the kept modals.

## Architecture

### Calendar data: client-side merge (no backend change)

The calendar needs both past (reported) and future (scheduled) days, but `/schedule` returns
only future-pending entries. We build a `Map<dateKey, CalendarEvent[]>` (dateKey =
`YYYY-MM-DD` of `fiscal_date`) by merging two endpoints already loaded by the page:

- **`/schedule` (pending/future)** → event `status: "scheduled"`; carries `eps_estimate`,
  `revenue_estimate`, `release_timing`; no report link.
- **`/runs` (past/live)** keyed by `fiscal_date` → `running` ⇒ `"live"`, `completed` ⇒
  `"reported"` (links to its report via the run's `report_id`), `failed` ⇒
  `"failed"` (rendered muted), `cancelled` omitted.

Per-event session (AM/PM) derives from `release_timing`: `{bmo, pre_market}` → AM,
`{amc, post_market, after_hours}` → PM, `null` → neutral. When one date carries both a schedule
entry and a run for the same ticker, the run wins and status precedence is
**live > reported > scheduled > failed**.

*Rejected alternatives:* a new backend `/calendar` endpoint (YAGNI; the v2 engine's
independence keeps this change frontend-only); extending `/schedule` to also return past/reported
rows (mutates a shipped contract and the weekly-sync semantics).

### Component strategy

Restyle the existing `feed/` components in place to the mockup's card/row styling, reusing
design tokens; remove the segmented filter; add new `calendar/` components, a view toggle, and
a merge hook. Existing modals and the report renderer are untouched.

## Page structure (new layout)

The page continues to render its own in-page header inside the global `AppLayout`/`Sidebar`
shell (unchanged pattern). Top to bottom:

1. **In-page topbar:** title "Earnings Update" · crumb "Department" · **live pill** ("N live"
   shown only when ≥1 run is `running`) · **Watchlist** button (with tracked count) ·
   **Generate report** (primary, opens `OnDemandReportModal`) · **Settings**.
2. **Hero:** eyebrow + headline + lede (editorial i18n text) + **three real count tiles** —
   Reports this week (completed runs in last 7 days), Tracked tickers (watchlist length),
   Upcoming this week (schedule entries with `scheduled_run_at` within 7 days). All derived
   from data already loaded; no extra fetch, no fabrication.
3. **View toggle:** Stream / Calendar (animated sliding pill, mockup styling).
4. **Search:** lightweight text input filtering the Stream feed by ticker/subject.
5. **Stream view** (restyled; metric columns removed):
   - *Live now* — `running` runs as a live card with SSE progress (sections written / tools
     inflight) + "Open update" + "Cancel" (reuses `useEuRunStream`).
   - *Earlier today* — runs created today → report rows (ticker · subject · time · status ·
     open/delete). No verdict/surprise columns.
   - *Up next · within 24h* — schedule pending soon → up-next cards with **real** Est. EPS /
     Est. Rev / session.
   - *Earlier this week* — completed runs from the last 7 days → report rows.
   - Per-section empty states (reuse existing i18n keys where present).
6. **Calendar view** (headline new feature):
   - Month grid (6 weeks / 42 cells), prev/next/Today nav, month label, four summary tiles
     (Reports / Pre-mkt / After-close / Live) computed for the visible month from the merged
     map.
   - Day cells: day number, Today pill, ≤3 event chips (ticker + AM/PM + status color),
     "+N more" overflow.
   - Day-detail popover: that day's events — ticker, company, session, time; reported/live
     events link to the report, scheduled events show est. EPS/Rev.
   - Caption: "Shows your watched and generated tickers."

## Files

**Modify / restyle:**
- `pages/departments/EarningsUpdate.tsx` — add `view` (stream|calendar) + `search` state, the
  three topbar buttons, calendar wiring; remove filter state.
- `feed/EuHero.tsx` — three real count tiles only.
- `feed/EuFeedSection.tsx`, `feed/EuBigCard.tsx` (live card), `feed/EuReportRow.tsx`,
  `feed/EuUpNextCard.tsx` — mockup styling; remove fabricated columns; up-next keeps real
  estimates.
- `feed/feedHelpers.ts` — keep date bucketing + search; remove segmented-filter logic.
- `feed/EuFilterStrip.tsx` — reduce to a search-only strip (or delete and host the search in
  the toggle row); the segmented control is removed.

**New:**
- `feed/EuViewToggle.tsx` — Stream/Calendar segmented toggle with sliding pill.
- `calendar/EuCalendar.tsx` — grid + nav + month summary.
- `calendar/EuCalendarDayPopover.tsx` — day-detail dialog.
- `calendar/calendarHelpers.ts` — pure logic: month-grid cell generation, session mapping,
  status precedence, summary counts, "+N more" overflow.
- `hooks/useEuCalendar.ts` — combines `useEuSchedule` + `useEuRuns` into the `Map<dateKey,
  CalendarEvent[]>` + month-navigation state.

**Keep as-is:** `WatchlistModal`, `ReportSettingsModal`, `OnDemandReportModal`,
`EuInstructionsUploadModal`, `EuTemplateUploadModal`, `EUCabinetView`, `EuModelPicker`,
`AddTickerPopover`, `EUV2ReportRenderer` + adapters, all existing `useEu*` hooks.

**i18n (`en.json` + `zh-TW.json`):** add `earnings.calendar.*` (months, day-of-week, legend,
summary labels, popover, watchlist-only caption), `earnings.view.*` (stream/calendar),
`earnings.generate_report`, hero tile labels; remove dead segmented-filter keys.

## Data mapping (real fields only)

| UI element | Source | Fields |
|---|---|---|
| Live card | run `status==running` | ticker, subject, created_at, SSE progress |
| Report row | run | ticker, subject, status, created_at/completed_at, open/delete |
| Up-next card | schedule pending | ticker, fiscal_date, release_timing→Pre/After, scheduled_run_at time, eps_estimate, revenue_estimate |
| Hero tiles | runs + watchlist + schedule | counts only (no fabrication) |
| Calendar event | schedule (scheduled) + runs (live/reported/failed) | keyed by fiscal_date; session from release_timing; report link when report_id present; est. EPS/Rev for scheduled |

## Edge cases

- Department disabled (503) → existing disabled banner; page does not crash.
- Load failure → error banner + Retry.
- Empty watchlist / empty feed → empty states.
- Empty calendar month → grid renders with no chips; summary tiles show 0.
- Live SSE failure → live card shows error, feed otherwise intact.
- Watched ticker with no schedule yet → calendar simply omits it (no event).
- A run whose `fiscal_date` is null → excluded from the calendar (can't place it); still shown
  in the Stream feed by `created_at`.

## Testing (co-located, matches existing `__tests__/` convention)

- `calendar/calendarHelpers.test.ts` (pure): 42-cell grid for a month incl. leading/trailing
  days; today marker; session mapping (bmo/amc/pre/post/after/null); status precedence
  (live>reported>scheduled>failed); summary counts; "+N more" overflow at >3 events.
- `hooks/__tests__/useEuCalendar.test.tsx`: merges schedule + runs into the date map; failed
  muted; cancelled omitted; report_id linking; null-fiscal_date run excluded.
- `calendar/__tests__/EuCalendar.test.tsx` + `EuCalendarDayPopover.test.tsx`: render grid and
  popover from a fixture map; nav prev/next/Today; click day → popover.
- `feed/__tests__/EuViewToggle.test.tsx`: switches view, moves pill.
- Update `feed/__tests__/EuUpNextCard.test.tsx` (keeps real estimates), and add/adjust render
  tests for restyled `EuReportRow` / `EuBigCard` asserting fabricated fields are absent.
- Update `pages/departments/EarningsUpdate.test.tsx`: view toggle present, filter removed,
  Generate-report button opens the modal, search filters the feed.

## Non-goals

- Any backend change (new endpoints, schema, or contract edits).
- A market-wide earnings calendar (backend has no such data; watchlist-only is intended).
- Reviving any fabricated metric (verdict pill, surprise %, after-hours, signal, sparkline).
- Restyling the kept modals or the shared report renderer.
- Reintroducing the segmented filter.
