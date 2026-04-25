import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

  describe("New badge", () => {
    beforeEach(() => {
      window.localStorage.clear();
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-04-25T12:00:00Z"));
    });

    afterEach(() => {
      vi.useRealTimers();
      window.localStorage.clear();
    });

    it("renders New dot for reports created within 24h", () => {
      const fresh = {
        id: "fresh",
        title: "Fresh report",
        subject: "AAPL",
        report_type: "earnings_update",
        created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      };
      render(
        <RecentReportsList
          reports={[fresh]}
          onOpenReport={() => {}}
          onOpenCabinet={() => {}}
        />,
      );
      expect(screen.getByLabelText(/new/i)).toBeInTheDocument();
    });

    it("does not render New dot for reports older than 24h", () => {
      const old = {
        id: "old",
        title: "Old report",
        subject: "AAPL",
        report_type: "earnings_update",
        created_at: new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString(),
      };
      render(
        <RecentReportsList
          reports={[old]}
          onOpenReport={() => {}}
          onOpenCabinet={() => {}}
        />,
      );
      expect(screen.queryByLabelText(/new/i)).toBeNull();
    });

    it("clears New dot after the report is opened", () => {
      const fresh = {
        id: "fresh",
        title: "Fresh report",
        subject: "AAPL",
        report_type: "earnings_update",
        created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      };
      render(
        <RecentReportsList
          reports={[fresh]}
          onOpenReport={() => {}}
          onOpenCabinet={() => {}}
        />,
      );
      expect(screen.getByLabelText(/new/i)).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: /^open$/i }));
      expect(screen.queryByLabelText(/new/i)).toBeNull();
    });
  });
});
