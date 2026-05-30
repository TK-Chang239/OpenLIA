import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunSummary } from "../../../api/earnings-update";
import { ReportRowItem } from "../ReportRowItem";

const baseReport: RunSummary = {
  report_id: "r1",
  ticker: "AAPL",
  subject: "Apple Inc. — Q1 FY2026 Earnings",
  template_id: "eu_default",
  trigger_kind: "on_demand",
  fiscal_date: null,
  language: "en",
  length: "normal",
  status: "completed",
  created_at: "2026-04-09T12:00:00Z",
  completed_at: "2026-04-09T12:05:00Z",
  reasoning_effort: null,
};

describe("ReportRowItem", () => {
  it("renders ticker + subject + open button", () => {
    render(<ReportRowItem report={baseReport} onOpen={() => {}} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText(/Apple Inc/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open/i })).toBeInTheDocument();
  });

  it("date column has hidden sm:block classes for mobile responsiveness", () => {
    render(<ReportRowItem report={baseReport} onOpen={() => {}} />);
    const date = screen.getByText(/Apr 9/);
    expect(date.className).toContain("hidden");
    expect(date.className).toContain("sm:block");
  });

  it("renders New badge dot when isNew", () => {
    render(<ReportRowItem report={baseReport} onOpen={() => {}} isNew />);
    expect(screen.getByLabelText(/new/i)).toBeInTheDocument();
  });
});
