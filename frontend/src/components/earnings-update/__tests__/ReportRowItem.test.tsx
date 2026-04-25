import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReportRowItem } from "../ReportRowItem";

const baseReport = {
  id: "r1",
  title: "Apple Inc. — Q1 FY2026 Earnings",
  subject: "AAPL",
  report_type: "earnings_update",
  created_at: "2026-04-09T12:00:00Z",
};

describe("ReportRowItem", () => {
  it("renders subject + title + open button", () => {
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
