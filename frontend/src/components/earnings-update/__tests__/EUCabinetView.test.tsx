import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EUCabinetView } from "../EUCabinetView";

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
    created_at: "2026-03-08T12:00:00Z",
  },
];

describe("EUCabinetView", () => {
  it("groups reports by month", () => {
    render(
      <EUCabinetView
        reports={reports}
        onBack={() => {}}
        onOpenReport={() => {}}
        onDownload={() => {}}
        onRemove={async () => {}}
      />,
    );
    expect(screen.getByText(/April 2026/)).toBeInTheDocument();
    expect(screen.getByText(/March 2026/)).toBeInTheDocument();
  });

  it("search filters reports", () => {
    render(
      <EUCabinetView
        reports={reports}
        onBack={() => {}}
        onOpenReport={() => {}}
        onDownload={() => {}}
        onRemove={async () => {}}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/search reports/i), {
      target: { value: "tesla" },
    });
    expect(screen.queryByText(/Apple Inc\./)).toBeNull();
    expect(screen.getByText(/Tesla Inc\./)).toBeInTheDocument();
  });

  it("back button fires", () => {
    const onBack = vi.fn();
    render(
      <EUCabinetView
        reports={reports}
        onBack={onBack}
        onOpenReport={() => {}}
        onDownload={() => {}}
        onRemove={async () => {}}
      />,
    );
    fireEvent.click(screen.getByText(/Back to Earnings Updates/));
    expect(onBack).toHaveBeenCalled();
  });
});
