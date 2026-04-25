import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RecentReport } from "../../../api/morning-briefing";
import { MBReportCard } from "../MBReportCard";

const baseReport: RecentReport = {
  id: "r-1",
  title: "Morning Briefing",
  report_type: "morning_briefing",
  created_at: "2026-04-09T07:00:00Z",
};

describe("MBReportCard", () => {
  it("Open and Download targets are rendered", () => {
    const onOpen = vi.fn();
    render(
      <MBReportCard
        report={baseReport}
        onOpen={onOpen}
        now={new Date("2026-04-09T08:00:00Z")}
      />,
    );
    fireEvent.click(screen.getByTestId("mb-report-open"));
    expect(onOpen).toHaveBeenCalledWith(baseReport);
    const dl = screen.getByTestId("mb-report-download") as HTMLAnchorElement;
    expect(dl.href).toContain("/api/reports/r-1/export/pdf");
  });

  it("shows New badge when created_at < 1h and unopened, hides after Open", () => {
    const now = new Date("2026-04-09T07:30:00Z");
    render(
      <MBReportCard report={baseReport} onOpen={() => {}} now={now} />,
    );
    expect(screen.getByTestId("mb-report-new-badge")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mb-report-open"));
    expect(screen.queryByTestId("mb-report-new-badge")).not.toBeInTheDocument();
  });

  it("hides New badge for old reports", () => {
    render(
      <MBReportCard
        report={baseReport}
        onOpen={() => {}}
        now={new Date("2026-04-09T10:00:00Z")}
      />,
    );
    expect(screen.queryByTestId("mb-report-new-badge")).not.toBeInTheDocument();
  });
});
