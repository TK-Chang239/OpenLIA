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

  test("a failed run with no completed run → 'queued'", () => {
    const g = coverageGroups([entry("GOOG")], new Map(), [run("GOOG", "failed")], NOW);
    expect(bucket(g, "queued")?.items.map((i) => i.entry.ticker)).toEqual(["GOOG"]);
  });

  test("pending exactly 7 days out → 'queued' (boundary exclusive)", () => {
    const byTicker = new Map([["AMZN", sched("AMZN", 7)]]);
    const g = coverageGroups([entry("AMZN")], byTicker, [], NOW);
    expect(bucket(g, "queued")?.items.map((i) => i.entry.ticker)).toEqual(["AMZN"]);
  });
});
