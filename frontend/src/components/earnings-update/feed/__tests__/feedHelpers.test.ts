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
