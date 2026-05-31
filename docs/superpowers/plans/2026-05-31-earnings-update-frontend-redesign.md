# Earnings Update Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Stream/Calendar view toggle and a working month-grid earnings calendar to the Earnings Update v2 page, give the hero three real (non-fabricated) stat tiles, remove the segmented filter, and add a dedicated "Generate report" topbar button — all against the existing backend (no backend changes).

**Architecture:** The page already renders a clean, metric-free Stream feed (`feed/` components + `useEu*` hooks). We add a new `calendar/` unit (pure grid/merge helpers + a `useEuCalendar` hook + `EuCalendar`/day-popover components) and an `EuViewToggle`. The calendar is fed entirely client-side by merging the two endpoints the page already loads: `GET /schedule` (future-pending) → `scheduled` events, and `GET /runs` (past/live, keyed by `fiscal_date`) → `live`/`reported`/`failed` events. The page gains `view` state to switch Stream ⇄ Calendar.

**Tech Stack:** React 18 + TypeScript + Vite, Tailwind (CSS-variable design tokens in `frontend/src/styles/tokens.css`), `react-i18next` (en + zh-TW), Vitest + React Testing Library + jsdom. Run all commands from `frontend/`.

**Branch:** `feat/eu-frontend-redesign` (stacks on `feat/eu-v2-per-connector-routing`, PR #218). The design spec is `docs/superpowers/specs/2026-05-31-earnings-update-frontend-redesign-design.md`.

**Conventions you must follow:**
- Tests are co-located in a `__tests__/` folder next to the component, named `<Component>.test.tsx`. Pure helpers get `<file>.test.ts`.
- All user-facing strings come from i18n (`t("earnings....")`). Never hardcode UI English in a component.
- Styling uses Tailwind arbitrary values referencing CSS vars, e.g. `className="text-[--color-text-primary] border-[--color-border-subtle]"`. Match the patterns already in `feed/` components.
- No emojis anywhere.
- Run `npx vitest run <path>` for a single test file. Run `npm run lint` (which is `tsc --noEmit`) before each commit to catch type errors.
- **Sandbox note:** if any `npm`/`npx` command fails with "Operation not permitted" or a sandbox/network error, re-run that exact command with the sandbox disabled.

**Important type facts (verified against the codebase — do not deviate):**
- `RunSummary` (`src/api/earnings-update.ts`): `{ report_id: string; ticker: string; subject: string; template_id: string; trigger_kind: "scheduled" | "on_demand"; fiscal_date: string | null; language: string; length: string; status: "running" | "completed" | "failed"; created_at: string; completed_at: string | null; reasoning_effort: "medium" | "high" | null }`.
- `EuScheduleEntry`: `{ id: string; ticker: string; fiscal_date: string; release_timing: "pre_market" | "post_market" | null; eps_estimate: string | null; revenue_estimate: string | null; scheduled_run_at: string; status: "pending" | "reported" | "skipped"; attempts: number; report_id: string | null }`.
- `useEuSchedule()` returns `{ schedule, byTicker, loading, error, refresh }`.
- `useEuRuns()` returns `{ runs, loading, error, disabled, refresh }`.

---

## Task 1: Add new i18n keys (en + zh-TW)

Add the keys the new components and the reworked hero will read. Do **not** remove any keys yet (the existing `EuFilterStrip`/`EuHero` still reference the old ones until later tasks replace them). Removals happen in Tasks 7 and 8.

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Add the new English keys**

In `en.json`, inside the `"earnings"` object, add two new sibling sub-objects `"view"` and `"calendar"`, and add a top-level `"generate_report"` and `"live_pill"` key, plus two new `feed` stat labels. Insert `"view"` and `"calendar"` right after the existing `"feed"` object. Add `"generate_report"` and `"live_pill"` next to the existing top-level `"watchlist"`/`"settings"` keys. Add `"stat_tracked"` and `"stat_upcoming"` inside `"feed"`.

```jsonc
// inside "earnings", next to "watchlist"/"settings":
"generate_report": "Generate report",
"live_pill": "{{count}} live",
```

```jsonc
// inside "earnings.feed", next to "stat_reports_wk":
"stat_tracked": "Tracked",
"stat_upcoming": "Upcoming this wk",
```

```jsonc
// inside "earnings", as new siblings of "feed":
"view": {
  "stream": "Stream",
  "calendar": "Calendar",
  "aria": "View mode"
},
"calendar": {
  "prev_month": "Previous month",
  "next_month": "Next month",
  "today": "Today",
  "today_pill": "Today",
  "close": "Close",
  "more": "+{{count}} more",
  "summary_reports": "Reports",
  "summary_pre_market": "Pre-mkt",
  "summary_after_close": "After-close",
  "summary_live": "Live now",
  "legend_live": "Live · run in progress",
  "legend_reported": "Reported · update ready",
  "legend_pre_market": "Pre-market",
  "legend_after_close": "After-close",
  "session_am": "AM",
  "session_pm": "PM",
  "watchlist_only": "Shows your watched and generated tickers.",
  "pop_reports_one": "{{count}} report",
  "pop_reports_other": "{{count}} reports",
  "pop_pre_market": "Pre-market",
  "pop_after_close": "After-close",
  "pop_status_live": "Live",
  "pop_status_reported": "Reported",
  "pop_est_eps": "Est. EPS",
  "pop_est_rev": "Rev.",
  "pop_empty": "No earnings on this day",
  "empty_month": "No earnings this month"
}
```

- [ ] **Step 2: Add the matching Traditional-Chinese keys**

In `zh-TW.json`, inside `"earnings"`, mirror the same structure:

```jsonc
// inside "earnings", next to "watchlist"/"settings":
"generate_report": "生成報告",
"live_pill": "{{count}} 進行中",
```

```jsonc
// inside "earnings.feed", next to "stat_reports_wk":
"stat_tracked": "追蹤中",
"stat_upcoming": "本週即將發布",
```

```jsonc
// inside "earnings", as new siblings of "feed":
"view": {
  "stream": "動態",
  "calendar": "行事曆",
  "aria": "檢視模式"
},
"calendar": {
  "prev_month": "上個月",
  "next_month": "下個月",
  "today": "今天",
  "today_pill": "今天",
  "close": "關閉",
  "more": "+{{count}} 更多",
  "summary_reports": "報告",
  "summary_pre_market": "盤前",
  "summary_after_close": "盤後",
  "summary_live": "進行中",
  "legend_live": "進行中 · 報告生成中",
  "legend_reported": "已發布 · 報告就緒",
  "legend_pre_market": "盤前",
  "legend_after_close": "盤後",
  "session_am": "盤前",
  "session_pm": "盤後",
  "watchlist_only": "僅顯示您追蹤及已生成的股票。",
  "pop_reports_one": "{{count}} 份報告",
  "pop_reports_other": "{{count}} 份報告",
  "pop_pre_market": "盤前",
  "pop_after_close": "盤後",
  "pop_status_live": "進行中",
  "pop_status_reported": "已發布",
  "pop_est_eps": "預估 EPS",
  "pop_est_rev": "營收",
  "pop_empty": "當日無財報",
  "empty_month": "本月無財報"
}
```

- [ ] **Step 3: Verify both files are valid JSON**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json')); JSON.parse(require('fs').readFileSync('src/i18n/locales/zh-TW.json')); console.log('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "i18n(earnings): add calendar, view-toggle, and hero-tile keys"
```

---

## Task 2: Calendar pure helpers

Pure, dependency-free logic: merge schedule + runs into a date→events map, build a 42-cell month grid, and summarize a month. No React, no i18n. Fully unit-tested.

**Files:**
- Create: `frontend/src/components/earnings-update/calendar/calendarHelpers.ts`
- Test: `frontend/src/components/earnings-update/calendar/calendarHelpers.test.ts`

- [ ] **Step 1: Write the failing test**

Create `calendarHelpers.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { EuScheduleEntry, RunSummary } from "../../../api/earnings-update";

import {
  VISIBLE_CHIPS,
  buildEventMap,
  buildMonthCells,
  sessionFromTiming,
  summarizeMonth,
  toDateKey,
} from "./calendarHelpers";

function schedule(partial: Partial<EuScheduleEntry>): EuScheduleEntry {
  return {
    id: partial.id ?? "s1",
    ticker: partial.ticker ?? "AAPL",
    fiscal_date: partial.fiscal_date ?? "2026-04-30",
    release_timing: partial.release_timing ?? "pre_market",
    eps_estimate: partial.eps_estimate ?? null,
    revenue_estimate: partial.revenue_estimate ?? null,
    scheduled_run_at: partial.scheduled_run_at ?? "2026-04-30T11:30:00Z",
    status: partial.status ?? "pending",
    attempts: partial.attempts ?? 0,
    report_id: partial.report_id ?? null,
  };
}

function run(partial: Partial<RunSummary>): RunSummary {
  return {
    report_id: partial.report_id ?? "r1",
    ticker: partial.ticker ?? "MSFT",
    subject: partial.subject ?? "MSFT Q3 FY26 earnings",
    template_id: partial.template_id ?? "eu_default",
    trigger_kind: partial.trigger_kind ?? "scheduled",
    fiscal_date: partial.fiscal_date ?? "2026-04-29",
    language: partial.language ?? "en",
    length: partial.length ?? "normal",
    status: partial.status ?? "completed",
    created_at: partial.created_at ?? "2026-04-29T20:00:00Z",
    completed_at: partial.completed_at ?? "2026-04-29T20:04:00Z",
    reasoning_effort: partial.reasoning_effort ?? null,
  };
}

describe("toDateKey", () => {
  it("formats a local date as YYYY-MM-DD", () => {
    expect(toDateKey(new Date(2026, 3, 5))).toBe("2026-04-05");
  });
});

describe("sessionFromTiming", () => {
  it("maps pre_market to am, post_market to pm, null to tbd", () => {
    expect(sessionFromTiming("pre_market")).toBe("am");
    expect(sessionFromTiming("post_market")).toBe("pm");
    expect(sessionFromTiming(null)).toBe("tbd");
  });
});

describe("buildEventMap", () => {
  it("places pending schedule entries as scheduled events keyed by fiscal_date", () => {
    const map = buildEventMap([schedule({ fiscal_date: "2026-04-30" })], []);
    const events = map.get("2026-04-30") ?? [];
    expect(events).toHaveLength(1);
    expect(events[0].status).toBe("scheduled");
    expect(events[0].session).toBe("am");
    expect(events[0].ticker).toBe("AAPL");
  });

  it("maps run status to live/reported/failed and keys by fiscal_date", () => {
    const map = buildEventMap(
      [],
      [
        run({ report_id: "a", ticker: "MSFT", fiscal_date: "2026-04-29", status: "completed" }),
        run({ report_id: "b", ticker: "META", fiscal_date: "2026-04-29", status: "running" }),
        run({ report_id: "c", ticker: "SBUX", fiscal_date: "2026-04-29", status: "failed" }),
      ],
    );
    const byTicker = Object.fromEntries(
      (map.get("2026-04-29") ?? []).map((e) => [e.ticker, e.status]),
    );
    expect(byTicker).toEqual({ MSFT: "reported", META: "live", SBUX: "failed" });
  });

  it("excludes runs with a null fiscal_date", () => {
    const map = buildEventMap([], [run({ fiscal_date: null })]);
    expect(map.size).toBe(0);
  });

  it("prefers the run over a schedule entry for the same ticker+date (run wins)", () => {
    const map = buildEventMap(
      [schedule({ ticker: "AAPL", fiscal_date: "2026-04-30", status: "pending" })],
      [run({ ticker: "AAPL", fiscal_date: "2026-04-30", status: "running", report_id: "live1" })],
    );
    const events = map.get("2026-04-30") ?? [];
    expect(events).toHaveLength(1);
    expect(events[0].status).toBe("live");
    expect(events[0].reportId).toBe("live1");
  });

  it("sorts a day's events by status precedence then ticker", () => {
    const map = buildEventMap(
      [schedule({ ticker: "ZZZ", fiscal_date: "2026-04-30", status: "pending" })],
      [
        run({ ticker: "BBB", fiscal_date: "2026-04-30", status: "completed", report_id: "1" }),
        run({ ticker: "AAA", fiscal_date: "2026-04-30", status: "running", report_id: "2" }),
      ],
    );
    expect((map.get("2026-04-30") ?? []).map((e) => e.ticker)).toEqual(["AAA", "BBB", "ZZZ"]);
  });
});

describe("buildMonthCells", () => {
  it("returns 42 cells starting on the Sunday on/before the 1st", () => {
    const cells = buildMonthCells(2026, 3, new Map(), new Date(2026, 3, 30));
    expect(cells).toHaveLength(42);
    expect(cells[0].date.getDay()).toBe(0); // Sunday
    // April 1 2026 is a Wednesday, so the grid starts Sun Mar 29.
    expect(cells[0].dateKey).toBe("2026-03-29");
    expect(cells[3].dateKey).toBe("2026-04-01");
    expect(cells[3].inMonth).toBe(true);
    expect(cells[0].inMonth).toBe(false);
  });

  it("flags today and attaches events", () => {
    const map = buildEventMap([schedule({ fiscal_date: "2026-04-30" })], []);
    const cells = buildMonthCells(2026, 3, map, new Date(2026, 3, 30));
    const apr30 = cells.find((c) => c.dateKey === "2026-04-30");
    expect(apr30?.isToday).toBe(true);
    expect(apr30?.events).toHaveLength(1);
  });
});

describe("summarizeMonth", () => {
  it("counts total / pre-market / after-close / live for in-month cells only", () => {
    const map = buildEventMap(
      [
        schedule({ ticker: "A", fiscal_date: "2026-04-10", release_timing: "pre_market" }),
        schedule({ ticker: "B", fiscal_date: "2026-04-11", release_timing: "post_market" }),
        schedule({ ticker: "C", fiscal_date: "2026-03-31", release_timing: "pre_market" }),
      ],
      [run({ ticker: "D", fiscal_date: "2026-04-12", status: "running", report_id: "x" })],
    );
    const cells = buildMonthCells(2026, 3, map, new Date(2026, 3, 30));
    const summary = summarizeMonth(cells);
    expect(summary.total).toBe(3); // A, B, D in April; C is March (out of month)
    expect(summary.preMarket).toBe(1); // A
    expect(summary.afterClose).toBe(1); // B
    expect(summary.live).toBe(1); // D
  });
});

describe("VISIBLE_CHIPS", () => {
  it("is 3", () => {
    expect(VISIBLE_CHIPS).toBe(3);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/calendar/calendarHelpers.test.ts`
Expected: FAIL — cannot resolve `./calendarHelpers`.

- [ ] **Step 3: Implement the helpers**

Create `calendarHelpers.ts`:

```ts
import type {
  EuScheduleEntry,
  ReleaseTiming,
  RunSummary,
} from "../../../api/earnings-update";

export const VISIBLE_CHIPS = 3;

export type CalEventStatus = "live" | "reported" | "scheduled" | "failed";
export type CalSession = "am" | "pm" | "tbd";

export interface CalendarEvent {
  ticker: string;
  status: CalEventStatus;
  session: CalSession;
  dateKey: string;
  reportId: string | null;
  epsEstimate: string | null;
  revenueEstimate: string | null;
  subject: string | null;
}

export interface CalendarCell {
  date: Date;
  dateKey: string;
  inMonth: boolean;
  isToday: boolean;
  isWeekend: boolean;
  events: CalendarEvent[];
}

export interface MonthSummary {
  total: number;
  preMarket: number;
  afterClose: number;
  live: number;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

// fiscal_date / run fiscal_date may be "YYYY-MM-DD" or an ISO datetime;
// normalise to the date portion.
function normaliseDateKey(raw: string): string {
  return raw.slice(0, 10);
}

export function sessionFromTiming(timing: ReleaseTiming): CalSession {
  if (timing === "pre_market") return "am";
  if (timing === "post_market") return "pm";
  return "tbd";
}

const STATUS_RANK: Record<CalEventStatus, number> = {
  live: 0,
  reported: 1,
  scheduled: 2,
  failed: 3,
};

function runStatusToEvent(status: RunSummary["status"]): CalEventStatus {
  if (status === "running") return "live";
  if (status === "failed") return "failed";
  return "reported";
}

export function buildEventMap(
  schedule: EuScheduleEntry[],
  runs: RunSummary[],
): Map<string, CalendarEvent[]> {
  // Collect per date, deduping by ticker keeping the higher-precedence event.
  const byDate = new Map<string, Map<string, CalendarEvent>>();

  function put(dateKey: string, event: CalendarEvent): void {
    let perTicker = byDate.get(dateKey);
    if (!perTicker) {
      perTicker = new Map();
      byDate.set(dateKey, perTicker);
    }
    const existing = perTicker.get(event.ticker);
    if (!existing || STATUS_RANK[event.status] < STATUS_RANK[existing.status]) {
      perTicker.set(event.ticker, event);
    }
  }

  for (const s of schedule) {
    if (s.status !== "pending") continue;
    if (!s.fiscal_date) continue;
    const dateKey = normaliseDateKey(s.fiscal_date);
    put(dateKey, {
      ticker: s.ticker.toUpperCase(),
      status: "scheduled",
      session: sessionFromTiming(s.release_timing),
      dateKey,
      reportId: s.report_id,
      epsEstimate: s.eps_estimate,
      revenueEstimate: s.revenue_estimate,
      subject: null,
    });
  }

  for (const r of runs) {
    if (!r.fiscal_date) continue;
    const dateKey = normaliseDateKey(r.fiscal_date);
    put(dateKey, {
      ticker: r.ticker.toUpperCase(),
      status: runStatusToEvent(r.status),
      session: "tbd", // runs carry no release timing
      dateKey,
      reportId: r.report_id,
      epsEstimate: null,
      revenueEstimate: null,
      subject: r.subject,
    });
  }

  const result = new Map<string, CalendarEvent[]>();
  for (const [dateKey, perTicker] of byDate) {
    const events = [...perTicker.values()].sort((a, b) => {
      const rank = STATUS_RANK[a.status] - STATUS_RANK[b.status];
      if (rank !== 0) return rank;
      return a.ticker.localeCompare(b.ticker);
    });
    result.set(dateKey, events);
  }
  return result;
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function buildMonthCells(
  year: number,
  month: number,
  eventMap: Map<string, CalendarEvent[]>,
  today: Date,
): CalendarCell[] {
  const first = new Date(year, month, 1);
  const start = new Date(year, month, 1 - first.getDay());
  const cells: CalendarCell[] = [];
  for (let i = 0; i < 42; i++) {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const dateKey = toDateKey(date);
    const day = date.getDay();
    cells.push({
      date,
      dateKey,
      inMonth: date.getMonth() === month,
      isToday: sameDay(date, today),
      isWeekend: day === 0 || day === 6,
      events: eventMap.get(dateKey) ?? [],
    });
  }
  return cells;
}

export function summarizeMonth(cells: CalendarCell[]): MonthSummary {
  let total = 0;
  let preMarket = 0;
  let afterClose = 0;
  let live = 0;
  for (const cell of cells) {
    if (!cell.inMonth) continue;
    for (const e of cell.events) {
      total++;
      if (e.session === "am") preMarket++;
      if (e.session === "pm") afterClose++;
      if (e.status === "live") live++;
    }
  }
  return { total, preMarket, afterClose, live };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/calendar/calendarHelpers.test.ts`
Expected: PASS (all describe blocks green).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/calendar/calendarHelpers.ts frontend/src/components/earnings-update/calendar/calendarHelpers.test.ts
git commit -m "feat(earnings): calendar merge + month-grid pure helpers"
```

---

## Task 3: `useEuCalendar` hook

Turn schedule + runs (passed in as arguments — **the hook does not fetch**, the page already loads this data) into the event map plus month-navigation state. Thin wrapper over the Task 2 helpers. `EuCalendar` (Task 6) consumes this hook, so there is no duplicate fetch and no dead code.

**Files:**
- Create: `frontend/src/hooks/useEuCalendar.ts`
- Test: `frontend/src/hooks/__tests__/useEuCalendar.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `useEuCalendar.test.tsx`:

```tsx
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EuScheduleEntry, RunSummary } from "../../api/earnings-update";
import { useEuCalendar } from "../useEuCalendar";

const scheduleRows: EuScheduleEntry[] = [
  {
    id: "s1",
    ticker: "AAPL",
    fiscal_date: "2026-04-30",
    release_timing: "pre_market",
    eps_estimate: "1.50",
    revenue_estimate: "94.2B",
    scheduled_run_at: "2026-04-30T11:30:00Z",
    status: "pending",
    attempts: 0,
    report_id: null,
  },
];

const runRows: RunSummary[] = [
  {
    report_id: "r1",
    ticker: "MSFT",
    subject: "MSFT Q3 FY26 earnings",
    template_id: "eu_default",
    trigger_kind: "scheduled",
    fiscal_date: "2026-04-29",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-04-29T20:00:00Z",
    completed_at: "2026-04-29T20:04:00Z",
    reasoning_effort: null,
  },
];

describe("useEuCalendar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 3, 30, 12, 0, 0));
  });

  it("exposes a merged event map and a month anchored on today", () => {
    const { result } = renderHook(() => useEuCalendar(scheduleRows, runRows));
    expect(result.current.viewYear).toBe(2026);
    expect(result.current.viewMonth).toBe(3); // April (0-indexed)
    expect(result.current.eventMap.get("2026-04-30")?.[0].ticker).toBe("AAPL");
    expect(result.current.eventMap.get("2026-04-29")?.[0].status).toBe("reported");
  });

  it("builds 42 cells and a month summary", () => {
    const { result } = renderHook(() => useEuCalendar(scheduleRows, runRows));
    expect(result.current.cells).toHaveLength(42);
    expect(result.current.summary.total).toBe(2);
    expect(result.current.summary.preMarket).toBe(1);
  });

  it("navigates months with next/prev/today", () => {
    const { result } = renderHook(() => useEuCalendar(scheduleRows, runRows));
    act(() => result.current.nextMonth());
    expect(result.current.viewMonth).toBe(4); // May
    act(() => result.current.prevMonth());
    act(() => result.current.prevMonth());
    expect(result.current.viewMonth).toBe(2); // March
    act(() => result.current.goToday());
    expect(result.current.viewMonth).toBe(3); // back to April
  });

  it("wraps the year boundary", () => {
    const { result } = renderHook(() => useEuCalendar(scheduleRows, runRows));
    act(() => result.current.prevMonth()); // March
    act(() => result.current.prevMonth()); // Feb
    act(() => result.current.prevMonth()); // Jan
    act(() => result.current.prevMonth()); // Dec 2025
    expect(result.current.viewYear).toBe(2025);
    expect(result.current.viewMonth).toBe(11);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEuCalendar.test.tsx`
Expected: FAIL — cannot resolve `../useEuCalendar`.

- [ ] **Step 3: Implement the hook**

Create `useEuCalendar.ts`:

```ts
import { useCallback, useMemo, useState } from "react";

import type { EuScheduleEntry, RunSummary } from "../api/earnings-update";
import {
  buildEventMap,
  buildMonthCells,
  summarizeMonth,
  type CalendarCell,
  type CalendarEvent,
  type MonthSummary,
} from "../components/earnings-update/calendar/calendarHelpers";

export interface EuCalendarState {
  viewYear: number;
  viewMonth: number; // 0-indexed
  cells: CalendarCell[];
  summary: MonthSummary;
  eventMap: Map<string, CalendarEvent[]>;
  nextMonth: () => void;
  prevMonth: () => void;
  goToday: () => void;
}

export function useEuCalendar(
  schedule: EuScheduleEntry[],
  runs: RunSummary[],
): EuCalendarState {
  const today = useMemo(() => new Date(), []);
  const [anchor, setAnchor] = useState(
    () => new Date(today.getFullYear(), today.getMonth(), 1),
  );

  const eventMap = useMemo(
    () => buildEventMap(schedule, runs),
    [schedule, runs],
  );

  const cells = useMemo(
    () => buildMonthCells(anchor.getFullYear(), anchor.getMonth(), eventMap, today),
    [anchor, eventMap, today],
  );

  const summary = useMemo(() => summarizeMonth(cells), [cells]);

  const nextMonth = useCallback(() => {
    setAnchor((a) => new Date(a.getFullYear(), a.getMonth() + 1, 1));
  }, []);
  const prevMonth = useCallback(() => {
    setAnchor((a) => new Date(a.getFullYear(), a.getMonth() - 1, 1));
  }, []);
  const goToday = useCallback(() => {
    setAnchor(new Date(today.getFullYear(), today.getMonth(), 1));
  }, [today]);

  return {
    viewYear: anchor.getFullYear(),
    viewMonth: anchor.getMonth(),
    cells,
    summary,
    eventMap,
    nextMonth,
    prevMonth,
    goToday,
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEuCalendar.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useEuCalendar.ts frontend/src/hooks/__tests__/useEuCalendar.test.tsx
git commit -m "feat(earnings): useEuCalendar hook merging schedule + runs"
```

---

## Task 4: `EuViewToggle` component

A two-button Stream/Calendar segmented toggle with a sliding pill, mirroring the existing `EuFilterStrip` pill mechanics.

**Files:**
- Create: `frontend/src/components/earnings-update/feed/EuViewToggle.tsx`
- Test: `frontend/src/components/earnings-update/feed/__tests__/EuViewToggle.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `EuViewToggle.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import { EuViewToggle } from "../EuViewToggle";

describe("EuViewToggle", () => {
  it("renders both view tabs and marks the active one selected", () => {
    render(<EuViewToggle view="stream" onChange={() => {}} />);
    const stream = screen.getByRole("tab", { name: /stream/i });
    const calendar = screen.getByRole("tab", { name: /calendar/i });
    expect(stream).toHaveAttribute("aria-selected", "true");
    expect(calendar).toHaveAttribute("aria-selected", "false");
  });

  it("calls onChange with the clicked view", () => {
    const onChange = vi.fn();
    render(<EuViewToggle view="stream" onChange={onChange} />);
    fireEvent.click(screen.getByRole("tab", { name: /calendar/i }));
    expect(onChange).toHaveBeenCalledWith("calendar");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/feed/__tests__/EuViewToggle.test.tsx`
Expected: FAIL — cannot resolve `../EuViewToggle`.

- [ ] **Step 3: Implement the component**

Create `EuViewToggle.tsx`:

```tsx
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Calendar, List } from "lucide-react";
import { useTranslation } from "react-i18next";

export type EuView = "stream" | "calendar";

interface Props {
  view: EuView;
  onChange: (next: EuView) => void;
}

const VIEW_IDS: readonly EuView[] = ["stream", "calendar"];

export function EuViewToggle({ view, onChange }: Props) {
  const { t } = useTranslation();
  const btnRefs = useRef<Map<EuView, HTMLButtonElement>>(new Map());
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number } | null>(
    null,
  );

  useLayoutEffect(() => {
    const btn = btnRefs.current.get(view);
    if (btn) setPillStyle({ left: btn.offsetLeft, width: btn.offsetWidth });
  }, [view]);

  useEffect(() => {
    function onResize() {
      const btn = btnRefs.current.get(view);
      if (btn) setPillStyle({ left: btn.offsetLeft, width: btn.offsetWidth });
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [view]);

  return (
    <div
      role="tablist"
      aria-label={t("earnings.view.aria")}
      className="inline-flex p-[3px] border border-[--color-border-subtle] rounded-lg bg-[--color-bg-elevated] relative"
    >
      {pillStyle ? (
        <span
          aria-hidden
          className="absolute top-[3px] bottom-[3px] bg-[--color-text-primary] rounded-[5px] z-[1] pointer-events-none transition-[left,width] duration-[320ms] ease-[cubic-bezier(0.32,0.72,0,1)]"
          style={{ left: pillStyle.left, width: pillStyle.width }}
        />
      ) : null}
      {VIEW_IDS.map((id) => {
        const isOn = id === view;
        const Icon = id === "stream" ? List : Calendar;
        return (
          <button
            key={id}
            ref={(el) => {
              if (el) btnRefs.current.set(id, el);
            }}
            type="button"
            role="tab"
            aria-selected={isOn}
            data-view={id}
            onClick={() => onChange(id)}
            className={`relative z-[2] inline-flex items-center gap-1.5 bg-transparent border-0 px-3 py-1.5 text-[12.5px] cursor-pointer rounded-[5px] transition-colors duration-[220ms] ${
              isOn
                ? "text-[--color-bg-base]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]"
            }`}
          >
            <Icon size={13} />
            {t(`earnings.view.${id}`)}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/feed/__tests__/EuViewToggle.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/feed/EuViewToggle.tsx frontend/src/components/earnings-update/feed/__tests__/EuViewToggle.test.tsx
git commit -m "feat(earnings): Stream/Calendar view toggle"
```

---

## Task 5: `EuCalendarDayPopover` component

A dialog listing one day's events. Reported/live events are buttons that open the report; scheduled events show est. EPS/Rev.

**Files:**
- Create: `frontend/src/components/earnings-update/calendar/EuCalendarDayPopover.tsx`
- Test: `frontend/src/components/earnings-update/calendar/__tests__/EuCalendarDayPopover.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `EuCalendarDayPopover.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { CalendarEvent } from "../calendarHelpers";
import { EuCalendarDayPopover } from "../EuCalendarDayPopover";

const reported: CalendarEvent = {
  ticker: "MSFT",
  status: "reported",
  session: "tbd",
  dateKey: "2026-04-29",
  reportId: "r1",
  epsEstimate: null,
  revenueEstimate: null,
  subject: "MSFT Q3 FY26 earnings",
};

const scheduled: CalendarEvent = {
  ticker: "AAPL",
  status: "scheduled",
  session: "am",
  dateKey: "2026-04-30",
  reportId: null,
  epsEstimate: "1.50",
  revenueEstimate: "94.2B",
  subject: null,
};

describe("EuCalendarDayPopover", () => {
  it("renders nothing when dateKey is null", () => {
    const { container } = render(
      <EuCalendarDayPopover dateKey={null} events={[]} onClose={() => {}} onOpenReport={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lists the day's events and the report count", () => {
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-30"
        events={[reported, scheduled]}
        onClose={() => {}}
        onOpenReport={() => {}}
      />,
    );
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText(/2 reports/i)).toBeInTheDocument();
    expect(screen.getByText(/94.2B/)).toBeInTheDocument();
  });

  it("opens a report when a reported event is clicked", () => {
    const onOpenReport = vi.fn();
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-29"
        events={[reported]}
        onClose={() => {}}
        onOpenReport={onOpenReport}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /MSFT/ }));
    expect(onOpenReport).toHaveBeenCalledWith("r1");
  });

  it("calls onClose from the close button", () => {
    const onClose = vi.fn();
    render(
      <EuCalendarDayPopover
        dateKey="2026-04-30"
        events={[scheduled]}
        onClose={onClose}
        onOpenReport={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/calendar/__tests__/EuCalendarDayPopover.test.tsx`
Expected: FAIL — cannot resolve `../EuCalendarDayPopover`.

- [ ] **Step 3: Implement the component**

Create `EuCalendarDayPopover.tsx`:

```tsx
import { useEffect } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { CalendarEvent } from "./calendarHelpers";

interface Props {
  dateKey: string | null;
  events: CalendarEvent[];
  onClose: () => void;
  onOpenReport: (reportId: string) => void;
}

function formatDayHeading(dateKey: string, locale: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString(locale, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

export function EuCalendarDayPopover({ dateKey, events, onClose, onOpenReport }: Props) {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (dateKey) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dateKey, onClose]);

  if (!dateKey) return null;

  const count = events.length;
  const countLabel =
    count === 1
      ? t("earnings.calendar.pop_reports_one", { count })
      : t("earnings.calendar.pop_reports_other", { count });

  return (
    <>
      <div
        className="fixed inset-0 z-[60] bg-black/30"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={formatDayHeading(dateKey, i18n.language)}
        className="fixed z-[61] left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(440px,92vw)] max-h-[80vh] overflow-y-auto bg-[--color-bg-elevated] border border-[--color-border-secondary] rounded-[12px] shadow-xl"
      >
        <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-3 border-b border-[--color-border-subtle]">
          <div>
            <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-text-tertiary]">
              {formatDayHeading(dateKey, i18n.language)}
            </span>
            <h3 className="text-[16px] font-semibold text-[--color-text-primary] m-0 mt-0.5">
              {countLabel}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("earnings.calendar.close")}
            className="text-[--color-text-tertiary] hover:text-[--color-text-primary]"
          >
            <X size={18} />
          </button>
        </header>
        <div className="p-3 flex flex-col gap-2">
          {count === 0 ? (
            <p className="font-mono text-[11px] tracking-[0.1em] uppercase text-[--color-text-tertiary] text-center py-5">
              {t("earnings.calendar.pop_empty")}
            </p>
          ) : (
            events.map((e) => (
              <DayRow key={`${e.ticker}-${e.status}`} event={e} onOpenReport={onOpenReport} />
            ))
          )}
        </div>
      </div>
    </>
  );
}

function DayRow({
  event,
  onOpenReport,
}: {
  event: CalendarEvent;
  onOpenReport: (reportId: string) => void;
}) {
  const { t } = useTranslation();
  const sessionLabel =
    event.session === "am"
      ? t("earnings.calendar.pop_pre_market")
      : event.session === "pm"
        ? t("earnings.calendar.pop_after_close")
        : null;
  const openable = (event.status === "reported" || event.status === "live") && event.reportId;

  const inner = (
    <>
      <span className="font-mono text-[13px] font-semibold text-[--color-text-primary] w-[56px] shrink-0">
        {event.ticker}
      </span>
      <div className="min-w-0 flex-1">
        {event.subject ? (
          <p className="text-[13px] text-[--color-text-primary] m-0 truncate">
            {event.subject}
          </p>
        ) : null}
        <span className="font-mono text-[10px] tracking-[0.06em] text-[--color-text-tertiary]">
          {event.status === "live"
            ? t("earnings.calendar.pop_status_live")
            : event.status === "reported"
              ? t("earnings.calendar.pop_status_reported")
              : sessionLabel ?? ""}
          {event.epsEstimate || event.revenueEstimate ? (
            <>
              {sessionLabel ? " · " : ""}
              {t("earnings.calendar.pop_est_eps")} {event.epsEstimate ?? "—"} ·{" "}
              {t("earnings.calendar.pop_est_rev")} {event.revenueEstimate ?? "—"}
            </>
          ) : null}
        </span>
      </div>
    </>
  );

  if (openable) {
    return (
      <button
        type="button"
        onClick={() => onOpenReport(event.reportId as string)}
        className="flex items-center gap-3 text-left px-3 py-2.5 rounded-[8px] border border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-feedback-success] transition-colors duration-[--duration-normal]"
      >
        {inner}
      </button>
    );
  }
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-[8px] border border-[--color-border-subtle] bg-[--color-bg-base]">
      {inner}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/calendar/__tests__/EuCalendarDayPopover.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/calendar/EuCalendarDayPopover.tsx frontend/src/components/earnings-update/calendar/__tests__/EuCalendarDayPopover.test.tsx
git commit -m "feat(earnings): calendar day-detail popover"
```

---

## Task 6: `EuCalendar` component (grid + nav + summary)

The month view: header (prev/next/Today + month label + summary tiles), weekday row, 42-cell grid with event chips and "+N more", legend, and the watchlist-only caption. Owns the day-popover open state.

**Files:**
- Create: `frontend/src/components/earnings-update/calendar/EuCalendar.tsx`
- Test: `frontend/src/components/earnings-update/calendar/__tests__/EuCalendar.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `EuCalendar.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import type { EuScheduleEntry, RunSummary } from "../../../../api/earnings-update";
import { EuCalendar } from "../EuCalendar";

const schedule: EuScheduleEntry[] = [
  {
    id: "s1",
    ticker: "AAPL",
    fiscal_date: "2026-04-30",
    release_timing: "pre_market",
    eps_estimate: "1.50",
    revenue_estimate: "94.2B",
    scheduled_run_at: "2026-04-30T11:30:00Z",
    status: "pending",
    attempts: 0,
    report_id: null,
  },
];

const runs: RunSummary[] = [
  {
    report_id: "r1",
    ticker: "MSFT",
    subject: "MSFT Q3 FY26 earnings",
    template_id: "eu_default",
    trigger_kind: "scheduled",
    fiscal_date: "2026-04-29",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-04-29T20:00:00Z",
    completed_at: "2026-04-29T20:04:00Z",
    reasoning_effort: null,
  },
];

function renderCalendar(onOpenReport = vi.fn()) {
  return render(
    <EuCalendar schedule={schedule} runs={runs} onOpenReport={onOpenReport} />,
  );
}

describe("EuCalendar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 3, 30, 12, 0, 0));
  });

  it("renders the current month label and event chips", () => {
    renderCalendar();
    expect(screen.getByTestId("eu-cal-month").textContent).toMatch(/April 2026/i);
    expect(screen.getAllByText("AAPL").length).toBeGreaterThan(0);
    expect(screen.getAllByText("MSFT").length).toBeGreaterThan(0);
  });

  it("navigates to the next month and back to today", () => {
    renderCalendar();
    fireEvent.click(screen.getByRole("button", { name: /next month/i }));
    expect(screen.getByTestId("eu-cal-month").textContent).toMatch(/May 2026/i);
    fireEvent.click(screen.getByRole("button", { name: /today/i }));
    expect(screen.getByTestId("eu-cal-month").textContent).toMatch(/April 2026/i);
  });

  it("opens the day popover when a day with events is clicked", () => {
    renderCalendar();
    const cell = screen.getByTestId("eu-cal-cell-2026-04-30");
    fireEvent.click(cell);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/1 report/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/calendar/__tests__/EuCalendar.test.tsx`
Expected: FAIL — cannot resolve `../EuCalendar`.

- [ ] **Step 3: Implement the component**

Create `EuCalendar.tsx`:

```tsx
import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Crosshair } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { EuScheduleEntry, RunSummary } from "../../../api/earnings-update";
import { useEuCalendar } from "../../../hooks/useEuCalendar";

import {
  VISIBLE_CHIPS,
  type CalEventStatus,
  type CalendarEvent,
} from "./calendarHelpers";
import { EuCalendarDayPopover } from "./EuCalendarDayPopover";

interface Props {
  schedule: EuScheduleEntry[];
  runs: RunSummary[];
  onOpenReport: (reportId: string) => void;
}

const STATUS_DOT: Record<CalEventStatus, string> = {
  live: "bg-[--color-accent-primary]",
  reported: "bg-[--color-feedback-success]",
  scheduled: "bg-[--color-border-strong]",
  failed: "bg-[--color-feedback-error]",
};

function weekdayShortNames(locale: string): string[] {
  // 2026-03-01 is a Sunday; produce Sun..Sat in the active locale.
  const base = new Date(2026, 2, 1);
  return Array.from({ length: 7 }, (_, i) =>
    new Date(base.getFullYear(), base.getMonth(), base.getDate() + i).toLocaleDateString(
      locale,
      { weekday: "short" },
    ),
  );
}

export function EuCalendar({ schedule, runs, onOpenReport }: Props) {
  const { t, i18n } = useTranslation();
  const {
    viewYear,
    viewMonth,
    cells,
    summary,
    eventMap,
    nextMonth,
    prevMonth,
    goToday,
  } = useEuCalendar(schedule, runs);
  const [openDay, setOpenDay] = useState<string | null>(null);
  const dow = useMemo(() => weekdayShortNames(i18n.language), [i18n.language]);

  const monthLabel = new Date(viewYear, viewMonth, 1).toLocaleDateString(
    i18n.language,
    { month: "long", year: "numeric" },
  );

  function openReportFromPopover(reportId: string) {
    setOpenDay(null);
    onOpenReport(reportId);
  }

  return (
    <div>
      <div className="flex items-center gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label={t("earnings.calendar.prev_month")}
            onClick={prevMonth}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            aria-label={t("earnings.calendar.next_month")}
            onClick={nextMonth}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
          >
            <ChevronRight size={16} />
          </button>
        </div>
        <h2
          data-testid="eu-cal-month"
          className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary] m-0 capitalize"
        >
          {monthLabel}
        </h2>
        <button
          type="button"
          onClick={goToday}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[--color-border-subtle] text-[12.5px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
        >
          <Crosshair size={13} /> {t("earnings.calendar.today")}
        </button>
        <div className="flex-1" />
        <div className="flex gap-5">
          <Summary label={t("earnings.calendar.summary_reports")} value={summary.total} />
          <Summary label={t("earnings.calendar.summary_pre_market")} value={summary.preMarket} />
          <Summary label={t("earnings.calendar.summary_after_close")} value={summary.afterClose} />
          <Summary
            label={t("earnings.calendar.summary_live")}
            value={summary.live}
            tone={summary.live > 0 ? "live" : undefined}
          />
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px mb-1">
        {dow.map((name) => (
          <span
            key={name}
            className="font-mono text-[9.5px] tracking-[0.1em] uppercase text-[--color-text-tertiary] text-center py-1"
          >
            {name}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px bg-[--color-border-subtle] border border-[--color-border-subtle] rounded-[10px] overflow-hidden">
        {cells.map((cell) => {
          const visible = cell.events.slice(0, VISIBLE_CHIPS);
          const overflow = cell.events.length - visible.length;
          const clickable = cell.events.length > 0;
          return (
            <div
              key={cell.dateKey}
              data-testid={`eu-cal-cell-${cell.dateKey}`}
              onClick={clickable ? () => setOpenDay(cell.dateKey) : undefined}
              className={`min-h-[92px] p-1.5 flex flex-col gap-1 bg-[--color-bg-elevated] ${
                cell.inMonth ? "" : "opacity-40"
              } ${clickable ? "cursor-pointer hover:bg-[--color-surface-hover]" : ""}`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`font-mono text-[11px] ${
                    cell.isToday
                      ? "text-[--color-text-primary] font-semibold"
                      : "text-[--color-text-tertiary]"
                  }`}
                >
                  {cell.date.getDate()}
                </span>
                {cell.isToday ? (
                  <span className="font-mono text-[8px] tracking-[0.1em] uppercase px-1 py-0.5 rounded bg-[--color-accent-subtle] text-[--color-feedback-success]">
                    {t("earnings.calendar.today_pill")}
                  </span>
                ) : null}
              </div>
              <div className="flex flex-col gap-0.5">
                {visible.map((e) => (
                  <Chip key={`${e.ticker}-${e.status}`} event={e} t={t} />
                ))}
                {overflow > 0 ? (
                  <span className="font-mono text-[9px] text-[--color-text-tertiary] pl-0.5">
                    {t("earnings.calendar.more", { count: overflow })}
                  </span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3">
        <Legend dot={STATUS_DOT.live} label={t("earnings.calendar.legend_live")} />
        <Legend dot={STATUS_DOT.reported} label={t("earnings.calendar.legend_reported")} />
        <Legend dot={STATUS_DOT.scheduled} label={t("earnings.calendar.legend_pre_market")} />
      </div>
      <p className="font-mono text-[10px] tracking-[0.08em] text-[--color-text-tertiary] mt-2">
        {t("earnings.calendar.watchlist_only")}
      </p>

      <EuCalendarDayPopover
        dateKey={openDay}
        events={openDay ? eventMap.get(openDay) ?? [] : []}
        onClose={() => setOpenDay(null)}
        onOpenReport={openReportFromPopover}
      />
    </div>
  );
}

function Chip({
  event,
  t,
}: {
  event: CalendarEvent;
  t: (key: string) => string;
}) {
  const sessionLabel =
    event.session === "am"
      ? t("earnings.calendar.session_am")
      : event.session === "pm"
        ? t("earnings.calendar.session_pm")
        : "";
  return (
    <span className="flex items-center gap-1 px-1 py-0.5 rounded bg-[--color-bg-base] border border-[--color-border-subtle]">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[event.status]}`} />
      <span className="font-mono text-[9.5px] font-semibold text-[--color-text-primary] truncate">
        {event.ticker}
      </span>
      {sessionLabel ? (
        <span className="font-mono text-[8px] text-[--color-text-tertiary] ml-auto">
          {sessionLabel}
        </span>
      ) : null}
    </span>
  );
}

function Summary({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "live";
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9px] tracking-[0.1em] uppercase text-[--color-text-tertiary]">
        {label}
      </span>
      <span
        className={`font-mono text-[18px] tabular-nums leading-none ${
          tone === "live" ? "text-[--color-feedback-success]" : "text-[--color-text-primary]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[9.5px] tracking-[0.06em] uppercase text-[--color-text-tertiary]">
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/calendar/__tests__/EuCalendar.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/calendar/EuCalendar.tsx frontend/src/components/earnings-update/calendar/__tests__/EuCalendar.test.tsx
git commit -m "feat(earnings): month-grid calendar view"
```

---

## Task 7: Hero real tiles + search-only feed filtering

Replace the hero's fabricated tiles with three real counts, and reduce `feedHelpers` to search-only (drop the `FeedFilter` union and the always-false portfolio/beats/misses branches). The `EuFilterStrip` is removed entirely in Task 8 when the page is reworked.

**Files:**
- Modify: `frontend/src/components/earnings-update/feed/EuHero.tsx`
- Create: `frontend/src/components/earnings-update/feed/__tests__/EuHero.test.tsx`
- Modify: `frontend/src/components/earnings-update/feed/feedHelpers.ts`
- Create: `frontend/src/components/earnings-update/feed/__tests__/feedHelpers.test.ts`

- [ ] **Step 1: Write the failing hero test**

Create `EuHero.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import "../../../../i18n";
import { EuHero } from "../EuHero";

describe("EuHero", () => {
  it("renders three real stat tiles with provided values", () => {
    render(
      <EuHero reportsThisWeek={5} trackedTickers={12} upcomingThisWeek={3} watchlistEmpty={false} />,
    );
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    // No fabricated labels remain.
    expect(screen.queryByText(/beats/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/surprise/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/latency/i)).not.toBeInTheDocument();
  });

  it("renders an em-dash when a count is null", () => {
    render(
      <EuHero reportsThisWeek={null} trackedTickers={0} upcomingThisWeek={0} watchlistEmpty />,
    );
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/feed/__tests__/EuHero.test.tsx`
Expected: FAIL — `EuHero` does not accept `trackedTickers`/`upcomingThisWeek` (type error) or renders old labels.

- [ ] **Step 3: Rewrite `EuHero.tsx`**

Replace the entire file with:

```tsx
import { useTranslation } from "react-i18next";

interface Props {
  reportsThisWeek: number | null;
  trackedTickers: number | null;
  upcomingThisWeek: number | null;
  watchlistEmpty: boolean;
}

const DASH = "—";

export function EuHero({
  reportsThisWeek,
  trackedTickers,
  upcomingThisWeek,
  watchlistEmpty,
}: Props) {
  const { t } = useTranslation();
  const lede = watchlistEmpty
    ? t("earnings.feed.hero_lede_empty")
    : t("earnings.feed.hero_lede");

  return (
    <section className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-end pb-[22px] border-b border-[--color-border-subtle] mb-6">
      <div>
        <span
          className="inline-flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-feedback-success] mb-2.5"
          data-testid="eu-hero-eyebrow"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_0_4px_rgba(var(--color-accent-primary-rgb),0.18)]" />
          {t("earnings.feed.hero_eyebrow")} {String.fromCharCode(0xb7)}{" "}
          {t("earnings.feed.hero_dept")}
        </span>
        <h1 className="text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] m-0 mb-2 text-[--color-text-primary]">
          {t("earnings.feed.hero_headline")}
        </h1>
        <p className="text-base text-[--color-text-secondary] m-0 max-w-[620px] leading-[1.55]">
          {lede}
        </p>
      </div>
      <div className="flex gap-7">
        <Stat label={t("earnings.feed.stat_reports_wk")} value={reportsThisWeek ?? DASH} />
        <Stat label={t("earnings.feed.stat_tracked")} value={trackedTickers ?? DASH} />
        <Stat label={t("earnings.feed.stat_upcoming")} value={upcomingThisWeek ?? DASH} />
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9.5px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
        {label}
      </span>
      <span className="font-mono text-[22px] tabular-nums leading-none text-[--color-text-primary]">
        {value}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Run the hero test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/feed/__tests__/EuHero.test.tsx`
Expected: PASS.

- [ ] **Step 5: Write the failing feedHelpers test**

Create `feedHelpers.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { RunSummary } from "../../../../api/earnings-update";
import { groupReports, searchReports } from "../feedHelpers";

function run(partial: Partial<RunSummary>): RunSummary {
  return {
    report_id: partial.report_id ?? "r",
    ticker: partial.ticker ?? "AAPL",
    subject: partial.subject ?? "Apple Q2",
    template_id: "eu_default",
    trigger_kind: "on_demand",
    fiscal_date: null,
    language: "en",
    length: "normal",
    status: "completed",
    created_at: partial.created_at ?? new Date().toISOString(),
    completed_at: null,
    reasoning_effort: null,
  };
}

describe("searchReports", () => {
  it("returns all reports when the query is empty", () => {
    const reports = [run({ ticker: "AAPL" }), run({ ticker: "MSFT" })];
    expect(searchReports(reports, "")).toHaveLength(2);
  });

  it("filters by ticker substring, case-insensitively", () => {
    const reports = [run({ ticker: "AAPL" }), run({ ticker: "MSFT" })];
    expect(searchReports(reports, "msf").map((r) => r.ticker)).toEqual(["MSFT"]);
  });

  it("filters by subject substring", () => {
    const reports = [
      run({ ticker: "AAPL", subject: "Apple beats on Services" }),
      run({ ticker: "MSFT", subject: "Azure reaccelerates" }),
    ];
    expect(searchReports(reports, "azure").map((r) => r.ticker)).toEqual(["MSFT"]);
  });
});

describe("groupReports", () => {
  it("splits reports into today and earlier-this-week buckets", () => {
    const now = new Date(2026, 3, 30, 12, 0, 0);
    const reports = [
      run({ report_id: "today", created_at: new Date(2026, 3, 30, 9).toISOString() }),
      run({ report_id: "week", created_at: new Date(2026, 3, 28, 9).toISOString() }),
    ];
    const groups = groupReports(reports, now);
    expect(groups.today.map((r) => r.report_id)).toEqual(["today"]);
    expect(groups.earlierThisWeek.map((r) => r.report_id)).toEqual(["week"]);
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/components/earnings-update/feed/__tests__/feedHelpers.test.ts`
Expected: FAIL — `searchReports` is not exported.

- [ ] **Step 7: Rewrite `feedHelpers.ts`**

Replace the entire file with (drops `FeedFilter`/`applyFilter`, adds `searchReports`; `groupReports`, `tickerOf`, and the date helpers are unchanged):

```ts
import type { RunSummary } from "../../../api/earnings-update";

const DAY_MS = 24 * 60 * 60 * 1000;

export function startOfTodayLocal(now: Date = new Date()): number {
  const d = new Date(now);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

export function isToday(iso: string, now: Date = new Date()): boolean {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return false;
  return ts >= startOfTodayLocal(now);
}

export function isWithinLastWeek(iso: string, now: Date = new Date()): boolean {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return false;
  const start = startOfTodayLocal(now) - 6 * DAY_MS;
  return ts >= start;
}

export function tickerOf(report: RunSummary): string {
  return (report.ticker ?? "").toUpperCase();
}

export function searchReports(reports: RunSummary[], search: string): RunSummary[] {
  const q = search.trim().toUpperCase();
  if (!q) return reports;
  return reports.filter(
    (r) => tickerOf(r).includes(q) || (r.subject ?? "").toUpperCase().includes(q),
  );
}

export interface FeedGroups {
  today: RunSummary[];
  earlierThisWeek: RunSummary[];
}

export function groupReports(
  reports: RunSummary[],
  now: Date = new Date(),
): FeedGroups {
  const today: RunSummary[] = [];
  const earlierThisWeek: RunSummary[] = [];
  for (const r of reports) {
    if (isToday(r.created_at, now)) today.push(r);
    else if (isWithinLastWeek(r.created_at, now)) earlierThisWeek.push(r);
  }
  return { today, earlierThisWeek };
}
```

- [ ] **Step 8: Run the feedHelpers test to verify it passes**

Run: `cd frontend && npx vitest run src/components/earnings-update/feed/__tests__/feedHelpers.test.ts`
Expected: PASS.

Note: `EuFilterStrip.tsx` still imports `FeedFilter` from this file and will now fail typecheck. That is expected — it is deleted in Task 8. Do **not** run `npm run lint` at this task's commit; the page integration in Task 8 resolves it. The two test files above pass in isolation.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/earnings-update/feed/EuHero.tsx frontend/src/components/earnings-update/feed/feedHelpers.ts frontend/src/components/earnings-update/feed/__tests__/EuHero.test.tsx frontend/src/components/earnings-update/feed/__tests__/feedHelpers.test.ts
git commit -m "feat(earnings): hero real tiles + search-only feed filtering"
```

---

## Task 8: Page integration — view toggle, calendar, topbar Generate button + live pill

Wire everything into `EarningsUpdate.tsx`: add `view` state and a toolbar row (`EuViewToggle` + search input), render the calendar when `view === "calendar"`, add the topbar "Generate report" button and a live pill, feed the hero its three real counts, and delete `EuFilterStrip`. Update the page test.

**Files:**
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx`
- Delete: `frontend/src/components/earnings-update/feed/EuFilterStrip.tsx`
- Modify: `frontend/src/pages/departments/EarningsUpdate.test.tsx`

- [ ] **Step 1: Delete `EuFilterStrip.tsx`**

```bash
git rm frontend/src/components/earnings-update/feed/EuFilterStrip.tsx
```

- [ ] **Step 2: Rewrite `EarningsUpdate.tsx`**

Replace the entire file with the following. Changes from the current version: import `EuViewToggle`/`EuCalendar` and `Plus`/`FileBarChart` icons; drop `EuFilterStrip`, `applyFilter`, `FeedFilter`; add `view` and replace `filter` with search-only flow; compute `trackedTickers`, `upcomingThisWeek`, `liveCount`; add the topbar Generate button + live pill; render a toolbar row and the calendar.

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Briefcase,
  FileBarChart,
  Search,
  Settings as SettingsIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { deleteRun, type RunSummary } from "../../api/earnings-update";
import { WatchlistModal } from "../../components/earnings-update/WatchlistModal";
import { EUCabinetView } from "../../components/earnings-update/EUCabinetView";
import { OnDemandReportModal } from "../../components/earnings-update/OnDemandReportModal";
import { ReportSettingsModal } from "../../components/earnings-update/ReportSettingsModal";
import { EuCalendar } from "../../components/earnings-update/calendar/EuCalendar";
import { EuBigCard } from "../../components/earnings-update/feed/EuBigCard";
import { EuEmptyPage } from "../../components/earnings-update/feed/EuEmptyPage";
import {
  EuFeedSection,
  EuSectionEmpty,
} from "../../components/earnings-update/feed/EuFeedSection";
import { EuHero } from "../../components/earnings-update/feed/EuHero";
import { EuReportRow } from "../../components/earnings-update/feed/EuReportRow";
import { EuUpNextCard } from "../../components/earnings-update/feed/EuUpNextCard";
import { EuViewToggle, type EuView } from "../../components/earnings-update/feed/EuViewToggle";
import {
  groupReports,
  searchReports,
} from "../../components/earnings-update/feed/feedHelpers";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useEuRuns } from "../../hooks/useEuRuns";
import { useEuRunStream } from "../../hooks/useEuRunStream";
import { useEuSchedule } from "../../hooks/useEuSchedule";
import { useEuSettings } from "../../hooks/useEuSettings";
import { useEuWatchlist } from "../../hooks/useEuWatchlist";

interface LiveCard {
  ticker: string;
  reportId: string;
}

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function findRun(runs: RunSummary[], reportId: string): RunSummary | undefined {
  return runs.find((r) => r.report_id === reportId);
}

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      data-testid="eu-skeleton"
      className={`bg-[--color-surface-hover] rounded-[--radius-md] animate-pulse ${className}`}
    />
  );
}

export default function EarningsUpdate() {
  const { t } = useTranslation();
  const {
    entries,
    add,
    remove,
    loading: watchlistLoading,
    error: watchlistError,
    refresh: refreshWatchlist,
  } = useEuWatchlist();
  const {
    runs,
    refresh: refreshRuns,
    loading: runsLoading,
    error: runsError,
    disabled: runsDisabled,
  } = useEuRuns();
  const { settings, save: saveSettings, disabled: settingsDisabled } =
    useEuSettings();
  const { schedule, byTicker } = useEuSchedule();

  const [watchlistOpen, setWatchlistOpen] = useState(false);
  const [cabinetOpen, setCabinetOpen] = useState(false);
  const [onDemandOpen, setOnDemandOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [live, setLive] = useState<LiveCard | null>(null);
  const [view, setView] = useState<EuView>("stream");
  const [search, setSearch] = useState("");

  const fv = useFileViewer();
  const stream = useEuRunStream(live?.reportId ?? null);

  const openReport = useCallback(
    (reportId: string) => {
      const match = findRun(runs, reportId);
      fv.open({
        filename: match?.subject ?? "Earnings Update",
        kind: "report",
        metadata: match ? `EU v2 · ${match.ticker}` : "Earnings Update",
        source: { kind: "eu_v2_report", reportId },
      });
    },
    [fv, runs],
  );

  const removeReport = useCallback(
    async (reportId: string) => {
      await deleteRun(reportId);
      await refreshRuns();
    },
    [refreshRuns],
  );

  const retryFetch = useCallback(() => {
    void refreshWatchlist();
    void refreshRuns();
  }, [refreshWatchlist, refreshRuns]);

  useEffect(() => {
    if (stream.status === "completed") {
      void refreshRuns();
    }
  }, [stream.status, refreshRuns]);

  const filtered = useMemo(() => searchReports(runs, search), [runs, search]);
  const groups = useMemo(() => groupReports(filtered), [filtered]);
  const searching = search.trim().length > 0;

  const todayReports = useMemo(
    () =>
      live ? groups.today.filter((r) => r.report_id !== live.reportId) : groups.today,
    [groups.today, live],
  );

  const heroToday = !live && todayReports.length > 0 ? todayReports[0] : null;
  const restToday = heroToday ? todayReports.slice(1) : todayReports;

  const upNext = useMemo(
    () => schedule.filter((s) => s.status === "pending"),
    [schedule],
  );

  const reportsThisWeek = useMemo(() => {
    const now = Date.now();
    return runs.filter((r) => {
      const ts = new Date(r.created_at).getTime();
      return !Number.isNaN(ts) && now - ts < WEEK_MS;
    }).length;
  }, [runs]);

  const upcomingThisWeek = useMemo(() => {
    const now = Date.now();
    return schedule.filter((s) => {
      if (s.status !== "pending") return false;
      const ts = new Date(s.scheduled_run_at).getTime();
      return !Number.isNaN(ts) && ts - now < WEEK_MS && ts >= now;
    }).length;
  }, [schedule]);

  const liveCount = useMemo(
    () => runs.filter((r) => r.status === "running").length + (live ? 1 : 0),
    [runs, live],
  );

  const disabled = runsDisabled || settingsDisabled;
  const hasError = Boolean(watchlistError || runsError);
  const initialLoading = watchlistLoading || runsLoading;
  const allEmpty =
    !initialLoading &&
    !hasError &&
    !disabled &&
    entries.length === 0 &&
    runs.length === 0 &&
    !live;

  function formatHeroStamp(iso: string): string {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const date = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    const time = d
      .toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
      .replace(/^0/, "");
    return `${date} · ${time} ET`;
  }

  const liveTitle =
    stream.status === "completed"
      ? t("earnings.report_ready")
      : t("earnings.generating_report", { ticker: live?.ticker ?? "" });

  return (
    <div className="flex flex-col h-full">
      <header className="h-[52px] flex items-center gap-3 px-6 flex-shrink-0 border-b border-[--color-border-subtle]">
        <h1 className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
          {t("earnings.title")}
        </h1>
        <div className="flex-1" />
        {liveCount > 0 ? (
          <span
            data-testid="eu-live-pill"
            className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.08em] uppercase text-[--color-feedback-success]"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
            {t("earnings.live_pill", { count: liveCount })}
          </span>
        ) : null}
        <button
          type="button"
          onClick={() => setWatchlistOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <Briefcase size={13} /> {t("earnings.watchlist")}
          <span className="font-mono text-[10px] text-[--color-text-tertiary]">
            {entries.length}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setOnDemandOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal] text-[12.5px] font-medium"
        >
          <FileBarChart size={13} /> {t("earnings.generate_report")}
        </button>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          aria-label={t("earnings.report_settings_aria")}
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <SettingsIcon size={13} /> {t("earnings.settings")}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-8 pt-7 pb-16">
          {disabled ? (
            <div
              data-testid="eu-v2-disabled-banner"
              className="mb-4 flex items-center gap-3 border border-[--color-border-subtle] rounded-[--radius-md] px-4 py-2.5 text-sm text-[--color-text-secondary] bg-[--color-surface-hover]"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[--color-feedback-warning] flex-shrink-0" />
              {t("earnings.disabled_banner")}
            </div>
          ) : null}

          {hasError ? (
            <div
              role="alert"
              className="mb-4 flex items-center justify-between gap-4 border border-[--color-feedback-error] rounded-[--radius-md] px-4 py-2 text-sm text-[--color-feedback-error]"
            >
              <span>{t("earnings.load_failed")}</span>
              <button
                type="button"
                onClick={retryFetch}
                className="text-sm font-medium underline"
              >
                {t("earnings.retry")}
              </button>
            </div>
          ) : null}

          {initialLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-[140px]" />
              <Skeleton className="h-12" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          ) : allEmpty ? (
            <>
              <div className="animate-feed-fade-up">
                <EuHero
                  reportsThisWeek={null}
                  trackedTickers={null}
                  upcomingThisWeek={null}
                  watchlistEmpty
                />
              </div>
              <div className="animate-feed-fade-up" style={{ animationDelay: "120ms" }}>
                <EuEmptyPage onOpenWatchlist={() => setWatchlistOpen(true)} />
              </div>
            </>
          ) : (
            <>
              <div className="animate-feed-fade-up">
                <EuHero
                  reportsThisWeek={runs.length === 0 ? null : reportsThisWeek}
                  trackedTickers={entries.length}
                  upcomingThisWeek={upcomingThisWeek}
                  watchlistEmpty={entries.length === 0}
                />
              </div>

              <div
                className="animate-feed-fade-up flex items-center gap-2 flex-wrap mb-[22px]"
                style={{ animationDelay: "80ms" }}
              >
                <EuViewToggle view={view} onChange={setView} />
                <div className="flex-1" />
                {view === "stream" ? (
                  <div className="inline-flex items-center gap-2 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-[--color-bg-elevated] min-w-[220px]">
                    <Search size={13} className="text-[--color-text-tertiary]" />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder={t("earnings.feed.search_placeholder")}
                      aria-label={t("earnings.feed.search_aria")}
                      className="border-0 bg-transparent outline-none text-[13px] text-[--color-text-primary] w-full placeholder:text-[--color-text-tertiary]"
                    />
                  </div>
                ) : null}
              </div>

              {view === "calendar" ? (
                <div className="animate-feed-fade-up" style={{ animationDelay: "120ms" }}>
                  <EuCalendar
                    schedule={schedule}
                    runs={runs}
                    onOpenReport={openReport}
                  />
                </div>
              ) : (
                <>
                  <div
                    className="animate-feed-fade-up"
                    style={{ animationDelay: "160ms" }}
                  >
                    <EuFeedSection
                      label={t("earnings.today")}
                      count={todayReports.length + (live ? 1 : 0)}
                    >
                      {live ? (
                        <div className="mb-2">
                          <EuBigCard
                            ticker={live.ticker}
                            title={liveTitle}
                            status={stream.status === "completed" ? "complete" : "streaming"}
                            reportId={stream.status === "completed" ? live.reportId : null}
                            onOpen={openReport}
                          />
                        </div>
                      ) : null}
                      {heroToday ? (
                        <div className="mb-2">
                          <EuBigCard
                            ticker={heroToday.ticker}
                            title={heroToday.subject}
                            stamp={formatHeroStamp(heroToday.created_at)}
                            status="complete"
                            reportId={heroToday.report_id}
                            onOpen={openReport}
                          />
                        </div>
                      ) : null}
                      {todayReports.length === 0 && !live ? (
                        <EuSectionEmpty
                          message={
                            searching
                              ? t("earnings.no_matching_prints_today")
                              : t("earnings.no_prints_today")
                          }
                        />
                      ) : null}
                      {restToday.length > 0 ? (
                        <div className="flex flex-col gap-2">
                          {restToday.map((r) => (
                            <EuReportRow key={r.report_id} report={r} onOpen={openReport} />
                          ))}
                        </div>
                      ) : null}
                    </EuFeedSection>
                  </div>

                  <div
                    className="animate-feed-fade-up"
                    style={{ animationDelay: "240ms" }}
                  >
                    <EuFeedSection
                      label={t("earnings.up_next_24h")}
                      count={upNext.length}
                    >
                      {upNext.length === 0 ? (
                        <EuSectionEmpty message={t("earnings.no_upcoming_earnings")} />
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          {upNext.map((u) => (
                            <EuUpNextCard key={u.id} entry={u} />
                          ))}
                        </div>
                      )}
                    </EuFeedSection>
                  </div>

                  <div
                    className="animate-feed-fade-up"
                    style={{ animationDelay: "320ms" }}
                  >
                    <EuFeedSection
                      label={t("earnings.earlier_this_week")}
                      count={groups.earlierThisWeek.length}
                    >
                      {groups.earlierThisWeek.length === 0 ? (
                        <EuSectionEmpty
                          message={
                            searching
                              ? t("earnings.no_matching_prints")
                              : t("earnings.no_prints_this_week")
                          }
                        />
                      ) : (
                        <div className="flex flex-col gap-2">
                          {groups.earlierThisWeek.map((r) => (
                            <EuReportRow key={r.report_id} report={r} onOpen={openReport} />
                          ))}
                        </div>
                      )}
                    </EuFeedSection>
                  </div>

                  {runs.length > 0 ? (
                    <div className="mt-7 flex justify-center">
                      <button
                        type="button"
                        onClick={() => setCabinetOpen(true)}
                        className="font-mono text-[11px] tracking-[0.12em] uppercase text-[--color-text-secondary] hover:text-[--color-text-primary]"
                      >
                        {t("earnings.view_all_reports")}
                      </button>
                    </div>
                  ) : null}
                </>
              )}
            </>
          )}
        </div>
      </div>

      <WatchlistModal
        open={watchlistOpen}
        entries={entries}
        onClose={() => setWatchlistOpen(false)}
        onAdd={async (ticker) => {
          await add(ticker);
        }}
        onRemove={async (id) => {
          await remove(id);
        }}
        nextReleaseByTicker={byTicker}
      />

      <OnDemandReportModal
        open={onDemandOpen}
        watchlist={entries}
        onClose={() => setOnDemandOpen(false)}
        onStarted={(reportId, ticker) => {
          setLive({ reportId, ticker });
        }}
      />

      {cabinetOpen ? (
        <EUCabinetView
          reports={runs}
          onBack={() => setCabinetOpen(false)}
          onOpenReport={openReport}
          onRemove={async (id) => {
            await removeReport(id);
          }}
        />
      ) : null}

      {settingsOpen && settings ? (
        <ReportSettingsModal
          settings={settings}
          onClose={() => setSettingsOpen(false)}
          onSave={saveSettings}
        />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 3: Read the existing page test to see what it mocks**

Run: `cd frontend && cat src/pages/departments/EarningsUpdate.test.tsx`
Note the mock setup (it mocks the `useEu*` hooks and modals). You will adapt assertions, not the mocking strategy.

- [ ] **Step 4: Update `EarningsUpdate.test.tsx`**

Make these changes (keeping the file's existing mock scaffolding intact):
1. If it references `CoverageModal`, it should already be `WatchlistModal` on this branch — leave as-is.
2. Remove/replace any assertion that depends on the segmented filter (`filter_all`/`filter_watchlist` tabs) — those tabs no longer exist.
3. Add these assertions (place inside the existing top-level `describe`, using the test's existing render helper — call it `renderPage()` if present, otherwise `render(<EarningsUpdate />)` wrapped the same way the other tests do):

```tsx
it("shows the Generate report button and opens the on-demand modal", async () => {
  renderPage();
  const btn = await screen.findByRole("button", { name: /generate report/i });
  fireEvent.click(btn);
  // OnDemandReportModal is mocked; assert the page passes open=true.
  expect(screen.getByTestId("on-demand-modal-open")).toBeInTheDocument();
});

it("switches to the calendar view via the toggle", async () => {
  renderPage();
  fireEvent.click(await screen.findByRole("tab", { name: /calendar/i }));
  expect(screen.getByTestId("eu-cal-month")).toBeInTheDocument();
});

it("no longer renders the segmented report filter", async () => {
  renderPage();
  await screen.findByRole("tab", { name: /stream/i });
  expect(screen.queryByRole("tab", { name: /^watchlist$/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: /beats/i })).not.toBeInTheDocument();
});
```

If the existing `OnDemandReportModal` mock does not render a testid when `open`, update that mock in the test file to: `vi.mock("...OnDemandReportModal", () => ({ OnDemandReportModal: ({ open }: { open: boolean }) => open ? <div data-testid="on-demand-modal-open" /> : null }))`. If the test does **not** mock `EuCalendar`/`useEuSchedule`/`useEuRuns`, ensure `useEuSchedule`/`useEuRuns` mocks return arrays (they likely already do) so `EuCalendar` renders without throwing. If `EuCalendar` is heavy to render in the page test, mock it: `vi.mock("...calendar/EuCalendar", () => ({ EuCalendar: () => <div data-testid="eu-cal-month" /> }))` — the dedicated `EuCalendar.test.tsx` already covers its behavior.

- [ ] **Step 5: Run the page test**

Run: `cd frontend && npx vitest run src/pages/departments/EarningsUpdate.test.tsx`
Expected: PASS. If a pre-existing test asserted on the removed filter, it should now be updated/removed (Step 4.2).

- [ ] **Step 6: Typecheck the whole frontend**

Run: `cd frontend && npm run lint`
Expected: no errors. (This confirms `EuFilterStrip`'s deletion left no dangling imports and `FeedFilter`/`applyFilter` are gone everywhere.)

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src/pages/departments/EarningsUpdate.tsx frontend/src/pages/departments/EarningsUpdate.test.tsx
git commit -m "feat(earnings): Stream/Calendar page, Generate-report button, live pill"
```

---

## Task 9: Remove dead i18n keys + full suite green

Now that no component references them, remove the fabricated/filter i18n keys, then run the full frontend suite and typecheck.

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Confirm the dead keys are unreferenced**

Run: `cd frontend && grep -rEn "stat_beats_misses|stat_avg_surprise|stat_avg_latency|filter_all|filter_watchlist|filter_portfolio|filter_beats|filter_misses|filter_aria|ad_hoc" src --include=*.ts --include=*.tsx`
Expected: no matches (all references were removed in Tasks 7–8). If anything matches, fix that reference first.

- [ ] **Step 2: Delete the dead keys from both locale files**

From `earnings.feed` in **both** `en.json` and `zh-TW.json`, remove these keys: `stat_beats_misses`, `stat_avg_surprise`, `stat_avg_latency`, `filter_all`, `filter_watchlist`, `filter_portfolio`, `filter_beats`, `filter_misses`, `filter_aria`, `ad_hoc`, `ad_hoc_aria`. Leave `rev_surprise`, `eps_surprise`, `after_hours`, `lia_signal`, `verdict_label`, `rev_label`, `eps_label` only if still referenced (Step 1 grep covers the removed set; do not remove keys the grep did not clear).

- [ ] **Step 3: Validate JSON**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json')); JSON.parse(require('fs').readFileSync('src/i18n/locales/zh-TW.json')); console.log('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Run the full frontend test suite**

Run: `cd frontend && npm run test`
Expected: all tests pass (no failures). If a pre-existing unrelated test fails, note it but do not fix out-of-scope failures.

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npm run lint`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "chore(earnings): drop dead filter + fabricated-metric i18n keys"
```

---

## Final verification (after all tasks)

- [ ] Run `cd frontend && npm run test && npm run lint` — both green.
- [ ] Manual smoke (optional, requires the server): `npm run dev`, open the Earnings Update page, confirm: hero shows three real counts; the Stream/Calendar toggle switches views; the calendar shows watched/run tickers on their fiscal dates, month nav works, clicking a day opens the popover, a reported day opens its report; the topbar "Generate report" button opens the on-demand modal; the search box filters the stream; no segmented filter remains.

## Notes for the implementer

- The calendar deliberately shows only the user's watched/generated tickers — the backend has no market-wide calendar. That is by design (see the spec's "watchlist-only scope").
- Runs carry no release-timing, so reported/live calendar events render session-neutral (no AM/PM chip); only scheduled events show AM/PM. This is expected.
- Do not add any backend calls or endpoints. Everything is driven by the already-loaded `useEuSchedule` + `useEuRuns` data.
- Do not restyle or touch `WatchlistModal`, `ReportSettingsModal`, `OnDemandReportModal`, the instructions/template modals, `EUCabinetView`, or the report renderer.
