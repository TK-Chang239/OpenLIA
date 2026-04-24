import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RecentReportsList } from "../RecentReportsList";

const reports = [
  {
    id: "r1",
    title: "Apple Inc. — Q1 FY2026 Earnings",
    subject: "AAPL",
    report_type: "earnings_update",
    created_at: "2026-04-09T12:00:00Z",
  },
  {
    id: "r2",
    title: "Tesla Inc. — Q1 FY2026 Earnings",
    subject: "TSLA",
    report_type: "earnings_update",
    created_at: "2026-04-08T12:00:00Z",
  },
];

describe("RecentReportsList", () => {
  it("renders a row per report", () => {
    render(
      <RecentReportsList
        reports={reports}
        onOpenReport={() => {}}
        onOpenCabinet={() => {}}
      />,
    );
    expect(
      screen.getAllByRole("button", { name: /open/i }).length,
    ).toBeGreaterThanOrEqual(2);
  });

  it("empty state when no reports", () => {
    render(
      <RecentReportsList
        reports={[]}
        onOpenReport={() => {}}
        onOpenCabinet={() => {}}
      />,
    );
    expect(screen.getByText(/will appear here/i)).toBeInTheDocument();
  });

  it("Open Cabinet link calls onOpenCabinet", () => {
    const onOpenCabinet = vi.fn();
    render(
      <RecentReportsList
        reports={reports}
        onOpenReport={() => {}}
        onOpenCabinet={onOpenCabinet}
      />,
    );
    fireEvent.click(screen.getByText(/Open Cabinet/i));
    expect(onOpenCabinet).toHaveBeenCalled();
  });
});
