import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportCard } from "./ReportCard";

describe("ReportCard", () => {
  it("renders the mode title and subject line", () => {
    render(
      <ReportCard
        reportId="r1"
        mode="stock_update"
        subject="AAPL"
        companyName="Apple Inc."
        createdAt="2026-04-09T12:00:00Z"
        preview="Apple reported..."
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText(/stock update report/i)).toBeInTheDocument();
    expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
  });

  it("calls onOpen when Open Report is clicked", () => {
    const onOpen = vi.fn();
    render(
      <ReportCard
        reportId="r1"
        mode="stock_update"
        subject="AAPL"
        companyName="Apple Inc."
        createdAt="2026-04-09T12:00:00Z"
        preview="x"
        onOpen={onOpen}
        onDownload={() => {}}
        onSave={() => {}}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /open report/i }));
    expect(onOpen).toHaveBeenCalledWith("r1");
  });

  it("renders sector research label without companyName", () => {
    render(
      <ReportCard
        reportId="r2"
        mode="sector_research"
        subject="Semiconductors"
        companyName={null}
        createdAt="2026-04-09T12:00:00Z"
        preview="x"
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText(/sector research report/i)).toBeInTheDocument();
    expect(screen.getByText(/Semiconductors/)).toBeInTheDocument();
  });
});
