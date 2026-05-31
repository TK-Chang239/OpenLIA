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
      if (key === "reported") return (b.date ?? "").localeCompare(a.date ?? "");
      if (key === "soon" || key === "queued") {
        if (a.date && b.date) return a.date.localeCompare(b.date);
        if (a.date) return -1;
        if (b.date) return 1;
      }
      return a.entry.ticker.localeCompare(b.entry.ticker);
    });
    return { key, items: inBucket };
  });
}
