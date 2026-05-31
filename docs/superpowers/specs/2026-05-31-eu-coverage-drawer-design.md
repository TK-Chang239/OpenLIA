# Earnings Update — Watchlist Coverage Drawer

**Date:** 2026-05-31
**Status:** Approved design, pre-implementation
**Base branch:** `merge/eu-frontend-redesign` (PR #225 — the EU frontend redesign). Work happens on `feat/eu-coverage-drawer` branched from it.
**Scope:** Frontend only (React/TS). No API, core, or DB changes.

## Problem

Today the user's watchlist (the tickers they track) opens as a centered modal
(`WatchlistModal`) showing a flat add/remove list. A standalone mockup
(`Earnings Update (standalone).html`) replaces it with a right-slide **coverage
drawer**: a stats header, an add-ticker row, and tickers **grouped by earnings
timing** (live / reporting-soon / reported / queued). This reads as a focused
"tracking list" side panel rather than a generic modal.

Confirmed: the mockup uses the app's existing design tokens (`--color-*`,
`--font-mono`, accent `#D4FF00`) — a structural restyle, no recoloring. All
data needed to bucket tickers already exists in the redesign branch's hooks
(`useEuWatchlist`, `useEuSchedule`, and the live/reported/scheduled
classification in `useEuCalendar`). No backend work.

## Goals

- Replace the centered `WatchlistModal` with a right-slide `CoverageDrawer`.
- Group tracked tickers by earnings timing: Live now, Reporting soon, Reported,
  Queued.
- Show a stats strip (Tracked / This wk / Live now / Updated) derived from
  existing data.
- Keep add (input + button) and remove in the drawer.
- Match the mockup's drawer geometry/motion using existing tokens; respect
  `prefers-reduced-motion`.

## Non-goals

- No exchange or sector on rows (not in our data; deferred).
- No ticker autocomplete/suggestions (would need a search API).
- No backend, API, schema, or hook-data changes.
- No change to `WatchlistCard` / `WatchlistRow` (the inline carousel) — out of scope.

## Decisions (from brainstorming)

| Topic | Decision |
| --- | --- |
| Shape | Replace `WatchlistModal` with a right-slide `CoverageDrawer`. |
| Grouping | Bucket by earnings timing (live / soon / reported / queued). |
| Row fields | Available data only: ticker, company name, "when" status. No exchange/sector. |
| Header chrome | Stats strip + plain add-ticker input. No autocomplete. |
| Reported rows | Link to the generated report (an "Open report" affordance). |

## Architecture

### Components

- **`CoverageDrawer.tsx`** (new) — the right-slide panel. Owns the open/close
  shell (backdrop, slide transition, Esc + backdrop-click close), the header
  (eyebrow + title + close + add-ticker row), the stats strip, and the
  scrollable grouped list. Presentational; all data via props/hooks passed in.
- **`coverageGroups.ts`** (new) — a pure helper that takes the watchlist entries
  + schedule-by-ticker + runs and returns ordered, labeled buckets. No React;
  unit-tested in isolation.
- **`CoverageTickerRow`** — a row sub-component (can live inside
  `CoverageDrawer.tsx`): ticker, company name, "when" line, remove button, and
  (for reported) an open-report link.

### Drawer shell

Mirror the mockup `cov-panel`:

- Backdrop: `fixed inset-0 z-40 bg-[rgba(13,13,11,0.42)]`, fades in (200ms).
- Panel: `fixed inset-y-0 right-0 z-50 w-[460px] max-w-[92vw]`, `bg-[--color-bg-base]`,
  left border + `-8px 0 32px rgba(13,13,11,0.10)` shadow, slides
  `translateX(100%) → 0` over `280ms cubic-bezier(0.32, 0.72, 0, 1)`.
- Reuse the existing `ol-drawer-in` keyframe / `HoldingDetailDrawer` pattern if
  present; otherwise add a slide-in keyframe to `tailwind.config.ts`.
- Under `prefers-reduced-motion: reduce`, the panel appears without the slide.

### Header

- Eyebrow (mono, uppercase, tertiary): `EARNINGS UPDATE · COVERAGE`.
- Title: "Tracking list".
- Close button (X), top-right.
- Add-ticker row: a text input (uppercased, ticker-validated — reuse the
  cleaning/validation from `AddTickerPopover`) + an accent `Add` button. On
  submit, calls `useEuWatchlist.add(ticker)`; shows the existing add error
  inline. No autocomplete.

### Stats strip

A flex row of four stats (mono label + value), all derived client-side:

- **Tracked** — `entries.length`.
- **This wk** — count of tracked tickers whose next pending earnings
  (`useEuSchedule.byTicker`) falls within the next 7 days.
- **Live now** — count of tracked tickers with a running report.
- **Updated** — last watchlist sync/refresh time, formatted `HH:MM ET`. Source:
  the timestamp the watchlist hook already exposes (or the time of the last
  successful refresh); if none is available, omit this stat rather than fabricate.

### Buckets

`coverageGroups(entries, byTicker, runs)` returns buckets in this fixed order;
empty buckets are omitted from render:

1. **Live now** — ticker has a running report. Row "when": `Live · Call in progress`.
2. **Reporting soon** — next pending earnings within 7 days. "when":
   `May 01 · 16:00 ET` (date + pre/post-market label from `release_timing`).
3. **Reported** — a recent completed run / schedule `status: reported`. "when":
   `Apr 30 · Done`; row links to the report.
4. **Queued** — pending earnings beyond 7 days, or no schedule yet. "when":
   the scheduled date if known, else `Queued · awaiting schedule`.

Each bucket renders a mono section label + count, then its rows. Classification
reuses the same live/reported/scheduled logic `useEuCalendar` already applies so
the drawer and calendar agree.

### Rows

`ticker` (mono, prominent) · `company_name` · the bucket-specific "when" line ·
a remove (Trash) control revealed on hover that calls `useEuWatchlist.remove(id)`.
Reported rows include an "Open report" link/affordance to the run.

### Empty states

- No tracked tickers at all → a centered prompt in the list area inviting the
  user to add their first ticker (the add-ticker input stays in the header).
- A bucket with zero tickers → not rendered.

## Page integration

In `EarningsUpdate.tsx`:

- Replace the `WatchlistModal` mount with `CoverageDrawer`.
- The existing header "Watchlist" button (with its entry count) now toggles the
  drawer open. Keep the same `watchlistOpen` state (rename to `coverageOpen` for
  clarity).
- Pass the data the drawer needs: `useEuWatchlist` (entries, add, remove, error,
  last-sync), `useEuSchedule` (byTicker), and the runs/live source used for
  classification.

## Files

| File | Change |
| --- | --- |
| `frontend/src/components/earnings-update/CoverageDrawer.tsx` | New. The slide-in panel: shell, header, add-ticker, stats, grouped list, rows, empty states. |
| `frontend/src/components/earnings-update/coverageGroups.ts` | New. Pure bucket-classification helper. |
| `frontend/src/components/earnings-update/__tests__/CoverageDrawer.test.tsx` | New. |
| `frontend/src/components/earnings-update/__tests__/coverageGroups.test.ts` | New. |
| `frontend/src/pages/departments/EarningsUpdate.tsx` | Swap modal mount/trigger for the drawer; rename `watchlistOpen` → `coverageOpen`; wire data. |
| `frontend/src/components/earnings-update/WatchlistModal.tsx` | Delete. |
| `frontend/src/components/earnings-update/__tests__/WatchlistModal.test.tsx` | Delete (if present). |
| `frontend/tailwind.config.ts` | Add a right-slide keyframe only if `ol-drawer-in` (or equivalent) isn't already available. |

## Testing

- **`coverageGroups`** (pure): a ticker with a running run → Live; pending within
  7 days → Reporting soon; completed run / reported → Reported; pending later or
  no schedule → Queued; bucket ordering; empty input → no buckets; a ticker with
  no schedule entry → Queued.
- **`CoverageDrawer`**: renders the four bucket sections with correct counts from
  fixture data; stats strip shows Tracked/This-wk/Live-now; add-ticker calls
  `add` and surfaces an error; remove calls `remove`; empty watchlist shows the
  add-first prompt; Esc and backdrop-click invoke `onClose`; reported row exposes
  the open-report affordance.
- **Page**: the header button opens the drawer; `WatchlistModal` is no longer
  imported or rendered.
- Reduced-motion: with `prefers-reduced-motion: reduce`, no slide animation class
  is applied (assert via class presence / matchMedia mock).

## Risks / open points

- **"Updated" timestamp**: only render it if the watchlist hook actually exposes
  a last-sync time; otherwise omit (no fabricated value).
- **Bucket source for "live"**: confirm at implementation time which value the
  redesign branch exposes for an in-progress report (running run vs a `live`
  flag) and classify from it; this is the same source `useEuCalendar` uses.
- Deleting `WatchlistModal` removes the only current full-list view; the drawer
  fully replaces it, so no affordance is lost.
