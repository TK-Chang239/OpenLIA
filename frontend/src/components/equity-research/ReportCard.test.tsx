import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportCard } from "./ReportCard";

const baseProps = {
  reportId: "r1",
  mode: "stock_update" as const,
  subject: "AAPL",
  companyName: "Apple Inc.",
  createdAt: "2026-04-09T12:00:00Z",
  preview: "Apple reported...",
};

describe("ReportCard", () => {
  it("renders the mode title and subject line", () => {
    render(<ReportCard {...baseProps} onOpen={() => {}} onSave={() => {}} />);
    expect(screen.getByText(/stock update report/i)).toBeInTheDocument();
    expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
  });

  it("calls onOpen when Open Report is clicked", () => {
    const onOpen = vi.fn();
    render(<ReportCard {...baseProps} onOpen={onOpen} onSave={() => {}} />);
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
        onSave={() => {}}
      />,
    );
    expect(screen.getByText(/sector research report/i)).toBeInTheDocument();
    expect(screen.getByText(/Semiconductors/)).toBeInTheDocument();
  });

  it("renders a shared download button (delegated component)", () => {
    render(<ReportCard {...baseProps} onOpen={() => {}} onSave={() => {}} />);
    expect(
      screen.getByRole("button", { name: /download report/i }),
    ).toBeInTheDocument();
  });

  it("clicking Save flips the bookmark to saved", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ReportCard {...baseProps} onOpen={() => {}} onSave={onSave} />);
    const saveBtn = screen.getByRole("button", { name: /save to repo/i });
    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("r1");
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /saved to repo/i }),
      ).toBeInTheDocument();
    });
  });
});
