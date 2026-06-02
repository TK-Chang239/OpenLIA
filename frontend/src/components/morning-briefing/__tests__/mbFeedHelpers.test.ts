import { describe, expect, it } from "vitest";

import type { MbRunSummary } from "../../../api/morning-briefing";
import {
  groupReports,
  isToday,
  isWithinLastWeek,
  searchReports,
} from "../feed/mbFeedHelpers";

function run(over: Partial<MbRunSummary>): MbRunSummary {
  return {
    report_id: "r",
    subject: "Briefing",
    trigger_kind: "scheduled",
    schedule_id: null,
    template_id: "freeform",
    instructions_id: null,
    language: "en",
    length: "normal",
    status: "completed",
    created_at: new Date().toISOString(),
    completed_at: null,
    reasoning_effort: null,
    highlights: null,
    ...over,
  };
}

const NOW = new Date("2026-06-02T12:00:00");

describe("mbFeedHelpers date buckets", () => {
  it("isToday is true for the same calendar day", () => {
    expect(isToday("2026-06-02T01:00:00", NOW)).toBe(true);
    expect(isToday("2026-06-01T23:00:00", NOW)).toBe(false);
  });

  it("isWithinLastWeek excludes today and items older than 6 days", () => {
    expect(isWithinLastWeek("2026-06-02T01:00:00", NOW)).toBe(false); // today
    expect(isWithinLastWeek("2026-05-30T01:00:00", NOW)).toBe(true);
    expect(isWithinLastWeek("2026-05-20T01:00:00", NOW)).toBe(false); // older
  });
});

describe("groupReports", () => {
  it("splits into today / thisWeek / older", () => {
    const reports = [
      run({ report_id: "a", created_at: "2026-06-02T08:00:00" }),
      run({ report_id: "b", created_at: "2026-05-30T08:00:00" }),
      run({ report_id: "c", created_at: "2026-05-01T08:00:00" }),
    ];
    const g = groupReports(reports, NOW);
    expect(g.today.map((r) => r.report_id)).toEqual(["a"]);
    expect(g.thisWeek.map((r) => r.report_id)).toEqual(["b"]);
    expect(g.older.map((r) => r.report_id)).toEqual(["c"]);
  });
});

describe("searchReports", () => {
  it("filters by subject and subtitle, case-insensitive", () => {
    const reports = [
      run({ report_id: "a", subject: "Rate-cut hopes lift stocks" }),
      run({
        report_id: "b",
        subject: "Quiet open",
        highlights: { subtitle: "Oil rallies", rating: null, metrics: [] },
      }),
    ];
    expect(searchReports(reports, "RATE").map((r) => r.report_id)).toEqual([
      "a",
    ]);
    expect(searchReports(reports, "oil").map((r) => r.report_id)).toEqual([
      "b",
    ]);
    expect(searchReports(reports, "")).toHaveLength(2);
  });
});
