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
