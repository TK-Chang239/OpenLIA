# EU Coverage Drawer (Watchlist Redesign) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the centered `WatchlistModal` with a right-slide **coverage drawer** that lists the user's tracked tickers grouped by earnings timing (Live now / Reporting soon / Reported / Queued), with a stats strip and an inline add-ticker row.

**Architecture:** Frontend-only. A pure `coverageGroups` helper buckets watchlist entries using existing hook data (`useEuWatchlist` entries + `useEuSchedule.byTicker` + `useEuRuns` runs). A presentational `CoverageDrawer` renders the slide-in panel (reusing the existing `ol-drawer-in` keyframe + drawer pattern). `EarningsUpdate.tsx` swaps the modal for the drawer. No API/core/DB changes.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind + CSS custom-property tokens, lucide-react, react-i18next, Vitest + @testing-library/react. Frontend package manager: `npm` (run from `frontend/`).

**Base branch:** `feat/eu-coverage-drawer` (already created off `merge/eu-frontend-redesign` / PR #225).

**Spec:** `docs/superpowers/specs/2026-05-31-eu-coverage-drawer-design.md`

**Conventions:**
- Commands run from `frontend/`. Single-file test: `npx vitest run <path>`. Typecheck/build: `npm run build`.
- EU components live in `frontend/src/components/earnings-update/`; tests in its `__tests__/`.
- Reuse design tokens (`--color-*`, `--font-mono`); never hardcode hex where a token exists.
- The `ol-drawer-in` keyframe already exists in `frontend/src/styles/global.css` — do NOT add a new keyframe.

---

## Reference: existing types (already defined, do not redefine)

From `frontend/src/api/earnings-update.ts`:
```ts
type RunStatus = "running" | "completed" | "failed";
type ScheduleStatus = "pending" | "reported" | "skipped";
type ReleaseTiming = "pre_market" | "post_market" | null;
interface WatchlistEntry { id: string; ticker: string; company_name: string | null; created_at: string; }
interface EuScheduleEntry { id: string; ticker: string; fiscal_date: string; release_timing: ReleaseTiming;
  eps_estimate: string | null; revenue_estimate: string | null; scheduled_run_at: string;
  status: ScheduleStatus; attempts: number; report_id: string | null; }
interface RunSummary { report_id: string; ticker: string; subject: string; /* … */ fiscal_date: string | null;
  status: RunStatus; created_at: string; completed_at: string | null; /* … */ }
```

---

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `frontend/src/components/earnings-update/coverageGroups.ts` | Pure helper: bucket watchlist entries into Live/Soon/Reported/Queued from entries + byTicker + runs. | Create |
| `frontend/src/components/earnings-update/CoverageDrawer.tsx` | Right-slide panel: header + add-ticker + stats strip + grouped rows + empty states. | Create |
| `frontend/src/components/earnings-update/__tests__/coverageGroups.test.ts` | Unit tests for the helper. | Create |
| `frontend/src/components/earnings-update/__tests__/CoverageDrawer.test.tsx` | Component tests. | Create |
| `frontend/src/i18n/locales/en.json` | Add `earnings.coverage.*` keys. | Modify |
| `frontend/src/i18n/locales/zh-TW.json` | Add `earnings.coverage.*` keys (Traditional Chinese). | Modify |
| `frontend/src/pages/departments/EarningsUpdate.tsx` | Swap `WatchlistModal` mount + trigger for `CoverageDrawer`; rename `watchlistOpen`→`coverageOpen`. | Modify |
| `frontend/src/components/earnings-update/WatchlistModal.tsx` | Delete. | Delete |
| `frontend/src/components/earnings-update/__tests__/WatchlistModal.test.tsx` | Delete (if present). | Delete |

---

## Task 1: `coverageGroups` — bucket classifier

Pure function (no React) that turns the watchlist into ordered, labeled buckets. Tested in isolation with a fixed `now`.

**Files:**
- Create: `frontend/src/components/earnings-update/coverageGroups.ts`
- Test: `frontend/src/components/earnings-update/__tests__/coverageGroups.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/earnings-update/__tests__/coverageGroups.test.ts`:

```ts
import { describe, expect, test } from "vitest";

import type { EuScheduleEntry, RunSummary, WatchlistEntry } from "../../../api/earnings-update";
import { coverageGroups } from "../coverageGroups";

const NOW = Date.parse("2026-05-01T12:00:00Z");

function entry(ticker: string): WatchlistEntry {
  return { id: `e-${ticker}`, ticker, company_name: `${ticker} Inc.`, created_at: "2026-04-01T00:00:00Z" };
}
function sched(ticker: string, daysFromNow: number): EuScheduleEntry {
  const at = new Date(NOW + daysFromNow * 86_400_000).toISOString();
  return {
    id: `s-${ticker}`, ticker, fiscal_date: at, release_timing: "pre_market",
    eps_estimate: null, revenue_estimate: null, scheduled_run_at: at,
    status: "pending", attempts: 0, report_id: null,
  };
}
function run(ticker: string, status: RunSummary["status"]): RunSummary {
  return {
    report_id: `r-${ticker}`, ticker, subject: `${ticker} earnings`, template_id: "t",
    trigger_kind: "scheduled", fiscal_date: null, language: "en", length: "normal",
    status, created_at: "2026-04-30T00:00:00Z", completed_at: "2026-04-30T01:00:00Z",
    reasoning_effort: null,
  } as RunSummary;
}

function bucket(groups: ReturnType<typeof coverageGroups>, key: string) {
  return groups.find((g) => g.key === key);
}

describe("coverageGroups", () => {
  test("a running run puts the ticker in 'live'", () => {
    const g = coverageGroups([entry("AAPL")], new Map(), [run("AAPL", "running")], NOW);
    expect(bucket(g, "live")?.items.map((i) => i.entry.ticker)).toEqual(["AAPL"]);
  });

  test("pending earnings within 7 days → 'soon' (with date + timing)", () => {
    const byTicker = new Map([["XOM", sched("XOM", 3)]]);
    const g = coverageGroups([entry("XOM")], byTicker, [], NOW);
    const item = bucket(g, "soon")?.items[0];
    expect(item?.entry.ticker).toBe("XOM");
    expect(item?.date).not.toBeNull();
    expect(item?.timing).toBe("pre_market");
  });

  test("a completed run (no upcoming-soon) → 'reported' with reportId", () => {
    const g = coverageGroups([entry("META")], new Map(), [run("META", "completed")], NOW);
    const item = bucket(g, "reported")?.items[0];
    expect(item?.entry.ticker).toBe("META");
    expect(item?.reportId).toBe("r-META");
  });

  test("pending beyond 7 days → 'queued'", () => {
    const byTicker = new Map([["NVDA", sched("NVDA", 21)]]);
    const g = coverageGroups([entry("NVDA")], byTicker, [], NOW);
    expect(bucket(g, "queued")?.items.map((i) => i.entry.ticker)).toEqual(["NVDA"]);
  });

  test("no schedule and no run → 'queued' with null date", () => {
    const g = coverageGroups([entry("TSM")], new Map(), [], NOW);
    const item = bucket(g, "queued")?.items[0];
    expect(item?.entry.ticker).toBe("TSM");
    expect(item?.date).toBeNull();
  });

  test("live takes precedence over a same-ticker upcoming schedule", () => {
    const byTicker = new Map([["AAPL", sched("AAPL", 2)]]);
    const g = coverageGroups([entry("AAPL")], byTicker, [run("AAPL", "running")], NOW);
    expect(bucket(g, "live")?.items).toHaveLength(1);
    expect(bucket(g, "soon")?.items ?? []).toHaveLength(0);
  });

  test("buckets are returned in fixed order live→soon→reported→queued", () => {
    const g = coverageGroups([], new Map(), [], NOW);
    expect(g.map((b) => b.key)).toEqual(["live", "soon", "reported", "queued"]);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run src/components/earnings-update/__tests__/coverageGroups.test.ts`
Expected: FAIL — "Cannot find module '../coverageGroups'".

- [ ] **Step 3: Implement the helper**

Create `frontend/src/components/earnings-update/coverageGroups.ts`:

```ts
import type {
  EuScheduleEntry,
  ReleaseTiming,
  RunSummary,
  WatchlistEntry,
} from "../../api/earnings-update";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export type CoverageBucketKey = "live" | "soon" | "reported" | "queued";

export interface CoverageItem {
  entry: WatchlistEntry;
  bucket: CoverageBucketKey;
  /** ISO date for the row's "when" line (fiscal/scheduled or completed). */
  date: string | null;
  /** Pre/post-market label source for "soon"/"queued" rows. */
  timing: ReleaseTiming;
  /** For "reported" rows: the run to open. */
  reportId: string | null;
}

export interface CoverageBucket {
  key: CoverageBucketKey;
  items: CoverageItem[];
}

const ORDER: CoverageBucketKey[] = ["live", "soon", "reported", "queued"];

function classify(
  entry: WatchlistEntry,
  byTicker: Map<string, EuScheduleEntry>,
  runs: RunSummary[],
  now: number,
): CoverageItem {
  const ticker = entry.ticker;

  const running = runs.find((r) => r.ticker === ticker && r.status === "running");
  if (running) {
    return { entry, bucket: "live", date: null, timing: null, reportId: running.report_id };
  }

  const sched = byTicker.get(ticker) ?? null;
  if (sched) {
    const ts = Date.parse(sched.scheduled_run_at);
    if (!Number.isNaN(ts) && ts - now < WEEK_MS && ts >= now) {
      return { entry, bucket: "soon", date: sched.fiscal_date, timing: sched.release_timing, reportId: null };
    }
  }

  // Most recent completed run for this ticker.
  const completed = runs
    .filter((r) => r.ticker === ticker && r.status === "completed")
    .sort((a, b) => (b.completed_at ?? b.created_at).localeCompare(a.completed_at ?? a.created_at))[0];
  if (completed) {
    return {
      entry,
      bucket: "reported",
      date: completed.completed_at ?? completed.fiscal_date,
      timing: null,
      reportId: completed.report_id,
    };
  }

  // Pending beyond a week, or nothing scheduled yet.
  return {
    entry,
    bucket: "queued",
    date: sched?.fiscal_date ?? null,
    timing: sched?.release_timing ?? null,
    reportId: null,
  };
}

export function coverageGroups(
  entries: WatchlistEntry[],
  byTicker: Map<string, EuScheduleEntry>,
  runs: RunSummary[],
  now: number,
): CoverageBucket[] {
  const items = entries.map((e) => classify(e, byTicker, runs, now));
  return ORDER.map((key) => {
    const inBucket = items.filter((i) => i.bucket === key);
    inBucket.sort((a, b) => {
      if (key === "reported") return (b.date ?? "").localeCompare(a.date ?? ""); // newest first
      if (key === "soon" || key === "queued") {
        if (a.date && b.date) return a.date.localeCompare(b.date); // soonest first
        if (a.date) return -1;
        if (b.date) return 1;
      }
      return a.entry.ticker.localeCompare(b.entry.ticker);
    });
    return { key, items: inBucket };
  });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npx vitest run src/components/earnings-update/__tests__/coverageGroups.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/coverageGroups.ts frontend/src/components/earnings-update/__tests__/coverageGroups.test.ts
git commit -m "feat(eu): coverageGroups watchlist bucket classifier"
```

---

## Task 2: i18n keys for the coverage drawer

Add the `earnings.coverage.*` keys the drawer renders, in both locales. (Add-ticker control reuses existing `earnings.add_ticker.*`; pre/post badge reuses `earnings.watchlist_card.pre_market`/`post_market`.)

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Add keys to `en.json`**

Find the `"earnings"` object. Inside it, add a `"coverage"` block (place it alongside the existing `"watchlist_modal"` / `"watchlist_card"` blocks — JSON object key order doesn't matter, but keep it inside `earnings`):

```json
"coverage": {
  "title": "Tracking list",
  "eyebrow": "Earnings Update · Coverage",
  "bucket_live": "Live now",
  "bucket_soon": "Reporting soon",
  "bucket_reported": "Reported",
  "bucket_queued": "Queued",
  "when_live": "Live · Call in progress",
  "when_done": "Done",
  "when_awaiting": "Awaiting schedule",
  "stat_tracked": "Tracked",
  "stat_this_week": "This wk",
  "stat_live": "Live now",
  "open_report": "Open report",
  "empty": "No tickers tracked yet. Add one above to start coverage.",
  "close_aria": "Close coverage drawer",
  "remove_aria": "Remove {{ticker}} from coverage"
}
```

Ensure the surrounding JSON stays valid (comma after the block if it is not the last key in `earnings`).

- [ ] **Step 2: Add the same keys to `zh-TW.json`** (Traditional Chinese)

```json
"coverage": {
  "title": "追蹤清單",
  "eyebrow": "財報更新 · 追蹤",
  "bucket_live": "進行中",
  "bucket_soon": "即將公布",
  "bucket_reported": "已公布",
  "bucket_queued": "排程中",
  "when_live": "進行中 · 財報會議中",
  "when_done": "完成",
  "when_awaiting": "等待排程",
  "stat_tracked": "追蹤中",
  "stat_this_week": "本週",
  "stat_live": "進行中",
  "open_report": "開啟報告",
  "empty": "尚未追蹤任何股票。在上方新增一檔以開始追蹤。",
  "close_aria": "關閉追蹤面板",
  "remove_aria": "將 {{ticker}} 從追蹤清單移除"
}
```

- [ ] **Step 3: Validate JSON**

Run (from repo root): `node -e "JSON.parse(require('fs').readFileSync('frontend/src/i18n/locales/en.json','utf8'));JSON.parse(require('fs').readFileSync('frontend/src/i18n/locales/zh-TW.json','utf8'));console.log('json ok')"`
Expected: `json ok`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "i18n(eu): coverage drawer keys (en + zh-TW)"
```

---

## Task 3: `CoverageDrawer` component

The right-slide panel. Presentational: receives entries/byTicker/runs + add/remove callbacks; computes buckets via `coverageGroups`.

**Files:**
- Create: `frontend/src/components/earnings-update/CoverageDrawer.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/CoverageDrawer.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/earnings-update/__tests__/CoverageDrawer.test.tsx`:

```tsx
import { describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { EuScheduleEntry, RunSummary, WatchlistEntry } from "../../../api/earnings-update";
import { CoverageDrawer } from "../CoverageDrawer";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o && "ticker" in o ? `${k}:${o.ticker}` : k,
  }),
}));

const NOW = Date.parse("2026-05-01T12:00:00Z");

function entry(t: string): WatchlistEntry {
  return { id: `e-${t}`, ticker: t, company_name: `${t} Inc.`, created_at: "2026-04-01T00:00:00Z" };
}
function run(t: string, status: RunSummary["status"]): RunSummary {
  return {
    report_id: `r-${t}`, ticker: t, subject: `${t} earnings`, template_id: "x",
    trigger_kind: "scheduled", fiscal_date: null, language: "en", length: "normal",
    status, created_at: "2026-04-30T00:00:00Z", completed_at: "2026-04-30T01:00:00Z", reasoning_effort: null,
  } as RunSummary;
}

function baseProps() {
  return {
    open: true,
    entries: [entry("AAPL"), entry("META")] as WatchlistEntry[],
    byTicker: new Map<string, EuScheduleEntry>(),
    runs: [run("AAPL", "running"), run("META", "completed")] as RunSummary[],
    now: NOW,
    onClose: vi.fn(),
    onAdd: vi.fn().mockResolvedValue(undefined),
    onRemove: vi.fn().mockResolvedValue(undefined),
  };
}

describe("CoverageDrawer", () => {
  test("renders bucket sections with the right tickers", () => {
    render(<CoverageDrawer {...baseProps()} />);
    expect(screen.getByTestId("coverage-bucket-live")).toHaveTextContent("AAPL");
    expect(screen.getByTestId("coverage-bucket-reported")).toHaveTextContent("META");
    // empty buckets omitted
    expect(screen.queryByTestId("coverage-bucket-soon")).toBeNull();
  });

  test("stats strip shows Tracked and Live-now counts", () => {
    render(<CoverageDrawer {...baseProps()} />);
    const stats = screen.getByTestId("coverage-stats");
    expect(stats).toHaveTextContent("2"); // tracked
  });

  test("add-ticker calls onAdd with the uppercased symbol", async () => {
    const props = baseProps();
    render(<CoverageDrawer {...props} />);
    fireEvent.change(screen.getByTestId("coverage-add-input"), { target: { value: "nvda" } });
    fireEvent.click(screen.getByTestId("coverage-add-btn"));
    await waitFor(() => expect(props.onAdd).toHaveBeenCalledWith("NVDA"));
  });

  test("remove calls onRemove with the entry id", () => {
    const props = baseProps();
    render(<CoverageDrawer {...props} />);
    fireEvent.click(screen.getByTestId("coverage-remove-e-AAPL"));
    expect(props.onRemove).toHaveBeenCalledWith("e-AAPL");
  });

  test("backdrop click and Escape both close", () => {
    const props = baseProps();
    render(<CoverageDrawer {...props} />);
    fireEvent.click(screen.getByTestId("coverage-backdrop"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(props.onClose).toHaveBeenCalledTimes(2);
  });

  test("empty watchlist shows the add-first prompt", () => {
    render(<CoverageDrawer {...baseProps()} entries={[]} runs={[]} />);
    expect(screen.getByTestId("coverage-empty")).toBeInTheDocument();
  });

  test("renders nothing when closed", () => {
    const { container } = render(<CoverageDrawer {...baseProps()} open={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run src/components/earnings-update/__tests__/CoverageDrawer.test.tsx`
Expected: FAIL — "Cannot find module '../CoverageDrawer'".

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/earnings-update/CoverageDrawer.tsx`:

```tsx
/**
 * CoverageDrawer — right-slide panel for the user's tracked tickers
 * ("coverage"). Replaces the centered WatchlistModal. Lists tickers
 * grouped by earnings timing (live / soon / reported / queued) with a
 * stats strip and an inline add-ticker row.
 */
import { Plus, Trash2, X } from "lucide-react";
import { type JSX, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  EuScheduleEntry,
  ReleaseTiming,
  RunSummary,
  WatchlistEntry,
} from "../../api/earnings-update";
import {
  type CoverageBucketKey,
  type CoverageItem,
  coverageGroups,
} from "./coverageGroups";

interface Props {
  open: boolean;
  entries: WatchlistEntry[];
  byTicker: Map<string, EuScheduleEntry>;
  runs: RunSummary[];
  onClose: () => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
  /** Optional open-report handler for reported rows. */
  onOpenReport?: (reportId: string) => void;
  /** Injectable clock for tests. */
  now?: number;
}

interface ErrorWithStatus {
  status?: number;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

const BUCKET_LABEL_KEY: Record<CoverageBucketKey, string> = {
  live: "earnings.coverage.bucket_live",
  soon: "earnings.coverage.bucket_soon",
  reported: "earnings.coverage.bucket_reported",
  queued: "earnings.coverage.bucket_queued",
};

export function CoverageDrawer({
  open,
  entries,
  byTicker,
  runs,
  onClose,
  onAdd,
  onRemove,
  onOpenReport,
  now,
}: Props): JSX.Element | null {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const clock = now ?? Date.now();
  const buckets = useMemo(
    () => coverageGroups(entries, byTicker, runs, clock),
    [entries, byTicker, runs, clock],
  );

  const trackedCount = entries.length;
  const liveCount = buckets.find((b) => b.key === "live")?.items.length ?? 0;
  const thisWeekCount = buckets.find((b) => b.key === "soon")?.items.length ?? 0;

  if (!open) return null;

  async function handleAdd() {
    setErr(null);
    const ticker = value.trim().toUpperCase();
    if (!ticker) return;
    setSubmitting(true);
    try {
      await onAdd(ticker);
      setValue("");
    } catch (e) {
      const status = (e as ErrorWithStatus).status;
      if (status === 409) setErr(t("earnings.add_ticker.already_watching", { ticker }));
      else if (status === 404) setErr(t("earnings.add_ticker.not_found", { ticker }));
      else setErr(t("earnings.add_ticker.add_failed"));
    } finally {
      setSubmitting(false);
    }
  }

  function whenText(item: CoverageItem): string {
    if (item.bucket === "live") return t("earnings.coverage.when_live");
    if (item.bucket === "reported") {
      return item.date ? `${formatDate(item.date)} · ${t("earnings.coverage.when_done")}` : t("earnings.coverage.when_done");
    }
    if (item.date) {
      const timing =
        item.timing === "pre_market"
          ? t("earnings.watchlist_card.pre_market")
          : item.timing === "post_market"
            ? t("earnings.watchlist_card.post_market")
            : null;
      return timing ? `${formatDate(item.date)} · ${timing}` : formatDate(item.date);
    }
    return t("earnings.coverage.when_awaiting");
  }

  const nonEmpty = buckets.filter((b) => b.items.length > 0);

  return (
    <div className="fixed inset-0 z-50" data-testid="coverage-drawer">
      <button
        type="button"
        data-testid="coverage-backdrop"
        aria-label={t("earnings.coverage.close_aria")}
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-[rgba(13,13,11,0.42)]"
      />
      <aside
        role="dialog"
        aria-label={t("earnings.coverage.title")}
        className="absolute right-0 top-0 flex h-full w-[460px] max-w-[92vw] flex-col border-l border-[--color-border-subtle] bg-[--color-bg-base] shadow-[-8px_0_32px_rgba(13,13,11,0.10)] motion-safe:animate-[ol-drawer-in_240ms_ease-out]"
      >
        {/* Header */}
        <header className="flex flex-col gap-[14px] border-b border-[--color-border-subtle] px-5 pb-[14px] pt-[18px]">
          <div className="flex items-start justify-between">
            <div>
              <p className="m-0 font-mono text-[9.5px] uppercase tracking-[0.14em] text-[--color-text-tertiary]">
                {t("earnings.coverage.eyebrow")}
              </p>
              <h2 className="m-0 mt-0.5 text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
                {t("earnings.coverage.title")}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("earnings.coverage.close_aria")}
              className="text-[--color-text-secondary] hover:text-[--color-text-primary]"
            >
              <X size={16} />
            </button>
          </div>
          <div className="flex items-stretch gap-1.5">
            <input
              data-testid="coverage-add-input"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleAdd();
              }}
              placeholder={t("earnings.add_ticker.placeholder")}
              className="h-[38px] flex-1 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 text-[13.5px] text-[--color-text-primary] outline-none transition-colors focus:border-[--color-text-secondary] focus:shadow-[0_0_0_3px_rgba(var(--color-accent-primary-rgb),0.10)]"
            />
            <button
              type="button"
              data-testid="coverage-add-btn"
              onClick={() => void handleAdd()}
              disabled={submitting}
              className="inline-flex h-[38px] items-center gap-1.5 rounded-md bg-[--color-accent-primary] px-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              <Plus size={13} /> {t("earnings.add_ticker.add")}
            </button>
          </div>
          {err ? <p className="m-0 text-xs text-[--color-feedback-error]">{err}</p> : null}
        </header>

        {/* Stats */}
        <div
          data-testid="coverage-stats"
          className="flex gap-[18px] border-b border-[--color-border-subtle] bg-[--color-bg-elevated] px-5 py-3"
        >
          <Stat label={t("earnings.coverage.stat_tracked")} value={trackedCount} />
          <Stat label={t("earnings.coverage.stat_this_week")} value={thisWeekCount} />
          <Stat label={t("earnings.coverage.stat_live")} value={liveCount} />
        </div>

        {/* List */}
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4 pt-1.5">
          {trackedCount === 0 ? (
            <p
              data-testid="coverage-empty"
              className="px-2 py-10 text-center text-[13px] text-[--color-text-tertiary]"
            >
              {t("earnings.coverage.empty")}
            </p>
          ) : (
            nonEmpty.map((b) => (
              <section key={b.key} data-testid={`coverage-bucket-${b.key}`} className="mb-3">
                <div className="flex items-center gap-2 px-2 py-1.5">
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                    {t(BUCKET_LABEL_KEY[b.key])}
                  </span>
                  <span className="font-mono text-[10px] text-[--color-text-tertiary]">{b.items.length}</span>
                </div>
                <ul className="flex flex-col">
                  {b.items.map((item) => (
                    <li
                      key={item.entry.id}
                      className="group flex items-center gap-3 rounded-md px-2 py-2 hover:bg-[--color-surface-hover]"
                    >
                      <span className="w-16 shrink-0 font-mono text-[13px] font-semibold text-[--color-text-primary]">
                        {item.entry.ticker}
                      </span>
                      <span className="flex-1 truncate text-[13px] text-[--color-text-secondary]">
                        {item.entry.company_name}
                      </span>
                      <span className="shrink-0 text-[11px] text-[--color-text-tertiary]">{whenText(item)}</span>
                      {item.reportId && onOpenReport ? (
                        <button
                          type="button"
                          onClick={() => onOpenReport(item.reportId as string)}
                          className="shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-feedback-success] hover:underline"
                        >
                          {t("earnings.coverage.open_report")}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        data-testid={`coverage-remove-${item.entry.id}`}
                        onClick={() => void onRemove(item.entry.id)}
                        aria-label={t("earnings.coverage.remove_aria", { ticker: item.entry.ticker })}
                        className="shrink-0 text-[--color-text-tertiary] opacity-0 transition-opacity hover:text-[--color-feedback-error] group-hover:opacity-100"
                      >
                        <Trash2 size={14} />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </div>
      </aside>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="flex flex-col gap-px">
      <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">{label}</span>
      <span className="text-[15px] font-semibold tabular-nums text-[--color-text-primary]">{value}</span>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npx vitest run src/components/earnings-update/__tests__/CoverageDrawer.test.tsx`
Expected: PASS (7 tests).

- [ ] **Step 5: Typecheck**

Run: `npx tsc --noEmit`
Expected: clean (the page still imports `WatchlistModal` at this point — that's fine; this step only confirms the new component compiles. If `tsc` flags the new files specifically, fix them; an unrelated pre-existing error elsewhere is acceptable and noted).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/earnings-update/CoverageDrawer.tsx frontend/src/components/earnings-update/__tests__/CoverageDrawer.test.tsx
git commit -m "feat(eu): CoverageDrawer slide-in panel"
```

---

## Task 4: Wire the drawer into the page; remove the modal

**Files:**
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx`
- Delete: `frontend/src/components/earnings-update/WatchlistModal.tsx`
- Delete: `frontend/src/components/earnings-update/__tests__/WatchlistModal.test.tsx` (if it exists)

- [ ] **Step 1: Swap the import**

In `EarningsUpdate.tsx`, replace the `WatchlistModal` import (line ~11):
```ts
import { WatchlistModal } from "../../components/earnings-update/WatchlistModal";
```
with:
```ts
import { CoverageDrawer } from "../../components/earnings-update/CoverageDrawer";
```

- [ ] **Step 2: Rename the open state**

Replace `const [watchlistOpen, setWatchlistOpen] = useState(false);` (line ~78) with:
```ts
const [coverageOpen, setCoverageOpen] = useState(false);
```
Then update the two trigger call sites:
- The header button `onClick={() => setWatchlistOpen(true)}` (line ~213) → `onClick={() => setCoverageOpen(true)}`.
- `<EuEmptyPage onOpenWatchlist={() => setWatchlistOpen(true)} />` (line ~284) → `onOpenWatchlist={() => setCoverageOpen(true)}` (keep `EuEmptyPage`'s prop name as-is; only the handler body changes).

- [ ] **Step 3: Replace the modal mount with the drawer**

Replace the `<WatchlistModal ... />` block (lines ~442-453):
```tsx
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
```
with:
```tsx
      <CoverageDrawer
        open={coverageOpen}
        entries={entries}
        byTicker={byTicker}
        runs={runs}
        onClose={() => setCoverageOpen(false)}
        onAdd={async (ticker) => {
          await add(ticker);
        }}
        onRemove={async (id) => {
          await remove(id);
        }}
        onOpenReport={openReport}
      />
```
(`runs`, `byTicker`, and `openReport` are all already in scope in the component — see lines ~68, ~76, ~88.)

- [ ] **Step 4: Delete the modal + its test**

```bash
git rm frontend/src/components/earnings-update/WatchlistModal.tsx
git rm frontend/src/components/earnings-update/__tests__/WatchlistModal.test.tsx 2>/dev/null || true
```
Then confirm nothing else imports it:
Run: `grep -rn "WatchlistModal" frontend/src` — expected: no matches. If any remain, remove those references.

- [ ] **Step 5: Typecheck + page-area tests**

Run: `npx tsc --noEmit` → expected clean.
Run: `npx vitest run src/pages/departments/EarningsUpdate.test.tsx` → expected PASS. If a test referenced `WatchlistModal` / the old modal testids (`watchlist-row`, etc.), update it to drive the drawer (open via the header button, assert `coverage-drawer` / `coverage-bucket-*`). Show the updated assertions rather than deleting coverage.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/departments/EarningsUpdate.tsx
git commit -m "feat(eu): open CoverageDrawer from the page; retire WatchlistModal"
```

---

## Task 5: Integration verification

**Files:** none (verification only)

- [ ] **Step 1: Full frontend suite**

Run: `npx vitest run`
Expected: PASS, no new failures (the pre-existing `SettingsShellBlocker` unhandled-rejection is unrelated — confirm the failure count is not higher than before this plan).

- [ ] **Step 2: Typecheck + build**

Run: `npm run build`
Expected: build succeeds, 0 TypeScript errors.

- [ ] **Step 3: Manual browser pass**

Start the app (backend on :8080 with `EARNINGS_ENGINE_VERSION=v2`, frontend `npm run dev`), open `/earnings-update`, click the **Watchlist** button. Confirm: the drawer slides in from the right; tickers are grouped (Live / Reporting soon / Reported / Queued) with correct "when" lines; the stats strip shows Tracked/This-wk/Live-now; adding a ticker works and errors surface; removing a ticker works; a reported row's "Open report" opens the report; Esc and backdrop close; an empty watchlist shows the add-first prompt; with OS "Reduce motion" on, the panel appears without the slide.

- [ ] **Step 4: Final commit (if manual-pass fixes were needed)**

```bash
git add -A
git commit -m "fix(eu): coverage drawer manual-pass adjustments"
```

---

## Self-Review Notes

- **Spec coverage:** drawer shell/geometry → Task 3; buckets → Task 1 (+ rendered in 3); row content/when → Task 3 (`whenText`); stats strip (Tracked/This-wk/Live-now, "Updated" omitted per the spec's no-timestamp fallback) → Task 3; add-ticker (reuses `earnings.add_ticker.*`) → Task 3; empty states → Task 3; page swap + modal delete → Task 4; reduced-motion via `motion-safe:` → Task 3.
- **"Updated" stat:** intentionally omitted — `useEuWatchlist` exposes no last-sync timestamp and the spec says omit rather than fabricate. Stats strip shows three values.
- **Type consistency:** `CoverageBucketKey`/`CoverageItem`/`CoverageBucket` defined in Task 1 are imported by Task 3; `coverageGroups(entries, byTicker, runs, now)` signature matches both the test and the component call. Bucket testids `coverage-bucket-{key}` and the keys `live|soon|reported|queued` are consistent across helper, component, and tests.
- **No backend/API/hook-data changes:** all data comes from existing `useEuWatchlist`/`useEuSchedule`/`useEuRuns`.
