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
    fiscal_date: "fiscal_date" in partial ? (partial.fiscal_date as string | null) : "2026-04-29",
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
