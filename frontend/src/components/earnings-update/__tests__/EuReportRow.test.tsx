import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunSummary } from "../../../api/earnings-update";
import { EuReportRow } from "../feed/EuReportRow";

function makeReport(highlights: RunSummary["highlights"]): RunSummary {
  return {
    report_id: "r1",
    ticker: "META",
    subject: "Q1 FY26 — Reality Labs narrows loss",
    template_id: "default",
    trigger_kind: "scheduled",
    fiscal_date: "2026-03-31",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-06-02T14:32:00Z",
    completed_at: "2026-06-02T14:36:00Z",
    reasoning_effort: null,
    highlights,
  };
}

describe("EuReportRow", () => {
  it("renders subtitle, up to 2 metric chips, and rating", () => {
    render(
      <EuReportRow
        report={makeReport({
          subtitle: "Reels CPMs up; capex guide raised",
          rating: "Buy",
          metrics: [
            { label: "Rev", value: "$36.5B", change: "+1.4%", tone: "positive" },
            { label: "EPS", value: "$5.16", change: "+5.2%", tone: "positive" },
            { label: "DAP", value: "3.31B", change: null, tone: "neutral" },
          ],
        })}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByTestId("eu-row-subtitle").textContent).toContain("Reels CPMs");
    expect(screen.getAllByTestId("eu-metric-chip")).toHaveLength(2);
    expect(screen.getByTestId("eu-rating-pill").textContent).toContain("Buy");
  });

  it("degrades to subject only when there are no highlights", () => {
    render(<EuReportRow report={makeReport(null)} onOpen={() => {}} />);
    expect(screen.getByText(/Reality Labs/)).toBeTruthy();
    expect(screen.queryByTestId("eu-row-subtitle")).toBeNull();
    expect(screen.queryByTestId("eu-metric-chip")).toBeNull();
  });
});
