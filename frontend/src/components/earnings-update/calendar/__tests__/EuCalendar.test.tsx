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

  it("opens the report and closes the popover when a reported row is clicked", () => {
    const onOpenReport = vi.fn();
    renderCalendar(onOpenReport);
    fireEvent.click(screen.getByTestId("eu-cal-cell-2026-04-29"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /msft/i }));
    expect(onOpenReport).toHaveBeenCalledWith("r1");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
