# Design: Refresh-now for Earnings Update release dates

Date: 2026-06-02
Status: Approved (brainstorm)
Surface: Earnings Update v2 department page

## Problem

The Earnings Update page populates its forward calendar of earnings release
dates from a weekly cron sync (Mondays 06:00 UTC) that reads each watchlist
ticker's next earnings date from EODHD. A user who just added tickers, or who
wants up-to-the-minute dates, has no way to trigger that sync on demand from
the UI. They wait up to a week.

## Goal

Add a "Refresh now" control to the Earnings Update page header that
immediately re-fetches each watchlist ticker's next earnings release date and
updates every on-screen release-date surface (calendar, up-next, coverage
drawer).

## What already exists (no backend work)

- Endpoint `POST /api/departments/earnings-update/v2/watchlist/sync` →
  `sync_watchlist()` → `calendar_sync.sync_user_watchlist(...)`. Iterates the
  user's `eu_v2_watchlist`, calls EODHD `earnings_calendar(ticker)`, upserts
  `eu_v2_earnings_schedule` rows (pending rows updated; reported/skipped left
  untouched). Returns `{ synced: N }`.
- API client `syncWatchlist(): Promise<{ synced: number }>`.
- `useEuSchedule()` exposes `refresh`; `useEuWatchlist()` exposes `refresh`.
- `EuCalendar`, `EuUpNextCard`, and `CoverageDrawer` all derive from the same
  `useEuSchedule()` state, so one schedule refresh updates them all.

This feature is therefore **frontend-only**.

## Design

### 1. New component: `EuRefreshButton`

Path: `frontend/src/components/earnings-update/EuRefreshButton.tsx`

A self-contained, isolated header control.

- Props:
  - `onRefresh: () => Promise<number>` — performs the sync + refresh, resolves
    to the synced ticker count.
  - `disabled?: boolean` — true when the watchlist is empty.
- Internal state: `idle | syncing | done | error`.
- Renders a `RefreshCw` (lucide) icon button styled to match the existing
  header buttons (`h-8`, subtle border, hover). Icon spins while `syncing`;
  button disabled while `syncing` or when `disabled`.
- Inline status text rendered left of the icon:
  - `done` → "Updated · {count} tickers"
  - `error` → "Refresh failed" (error color)
  - auto-clears back to `idle` after ~4s.
- When `disabled`, `title` = "Add tickers first".

Why a separate component: keeps behavior (state machine, auto-clear, error
handling) testable in isolation and keeps the already-large page file focused.

### 2. Page wiring: `EarningsUpdate.tsx`

- Pull `refresh: refreshSchedule` from `useEuSchedule()` (currently only
  `schedule`, `byTicker` are destructured).
- Add handler:
  ```ts
  const handleRefreshDates = useCallback(async () => {
    const { synced } = await syncWatchlist();
    await Promise.all([refreshWatchlist(), refreshSchedule()]);
    return synced;
  }, [refreshWatchlist, refreshSchedule]);
  ```
- Render `<EuRefreshButton onRefresh={handleRefreshDates}
  disabled={entries.length === 0} />` in the header, immediately before the
  Watchlist button.
- Remove the now-redundant unused `syncNow` from `useEuWatchlist` (it only
  refreshed the watchlist, never the schedule, and was never wired to UI). The
  page orchestrates the dual refresh because it is the only place that owns
  both the watchlist and schedule hooks.

### 3. i18n

Add keys under the `earnings` namespace to both `en.json` and `zh-TW.json`:

- `earnings.refresh.aria` — accessible label for the icon button
- `earnings.refresh.syncing` — "Refreshing…"
- `earnings.refresh.done` — "Updated · {{count}} tickers"
- `earnings.refresh.failed` — "Refresh failed"
- `earnings.refresh.empty_hint` — "Add tickers first" (disabled title)

## Edge cases

- Empty watchlist → button disabled, `title` = empty hint. Nothing to sync.
- EODHD not configured → endpoint returns `{ synced: 0 }` → "Updated · 0
  tickers". No error surfaced (mirrors server's loud-null transport choice).
- Sync error (network / 5xx) → `error` state, "Refresh failed" inline, icon
  reverts to idle.

## Testing

`frontend/src/components/earnings-update/__tests__/EuRefreshButton.test.tsx`:

- Click invokes `onRefresh`, shows the syncing state, then "Updated · N
  tickers" on resolve.
- `disabled` prop prevents the click handler from firing.
- `onRefresh` rejection renders "Refresh failed".

## Out of scope

- Weekly cron sync and hourly dispatch are unchanged.
- Watchlist only — no portfolio/holdings integration.
- No change to how reports are generated; this only refreshes release dates.

## Follow-up at implementation time

Update the living `planning/specs/pages/departments/EarningsUpdatePageSpec.md`
to document the header refresh control (per CLAUDE.md: keep specs in sync).
