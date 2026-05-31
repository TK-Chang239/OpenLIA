import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunSummary } from "../../../api/earnings-update";
import { RecentReportsList } from "../RecentReportsList";

function makeRun(over: Partial<RunSummary>): RunSummary {
  return {
    report_id: "r",
    ticker: "AAPL",
    subject: "Subject",
    template_id: "eu_default",
    trigger_kind: "on_demand",
    fiscal_date: null,
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-04-09T12:00:00Z",
    completed_at: null,
    reasoning_effort: null,
    ...over,
  };
}

const reports: RunSummary[] = [
  makeRun({
    report_id: "r1",
    subject: "Apple Inc. — Q1 FY2026 Earnings",
    ticker: "AAPL",
    created_at: "2026-04-09T12:00:00Z",
  }),
  makeRun({
    report_id: "r2",
    subject: "Tesla Inc. — Q1 FY2026 Earnings",
    ticker: "TSLA",
    created_at: "2026-04-08T12:00:00Z",
  }),
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
      const fresh = makeRun({
        report_id: "fresh",
        subject: "Fresh report",
        ticker: "AAPL",
        created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      });
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
      const old = makeRun({
        report_id: "old",
        subject: "Old report",
        ticker: "AAPL",
        created_at: new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString(),
      });
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
      const fresh = makeRun({
        report_id: "fresh",
        subject: "Fresh report",
        ticker: "AAPL",
        created_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      });
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
