import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnDemandReportModal } from "../OnDemandReportModal";

describe("OnDemandReportModal", () => {
  it("generate button disabled until ticker entered", () => {
    render(
      <OnDemandReportModal
        open
        onClose={() => {}}
        onReportReady={() => {}}
        startReport={async () => ({ report_id: "x", title: "t" })}
      />,
    );
    const btn = screen.getByRole("button", { name: /generate report/i });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/ticker/i), {
      target: { value: "AAPL" },
    });
    expect(btn).toBeEnabled();
  });

  it("calls startReport and onReportReady with result", async () => {
    const startReport = vi
      .fn()
      .mockResolvedValue({ report_id: "r_1", title: "AAPL" });
    const onReportReady = vi.fn();
    render(
      <OnDemandReportModal
        open
        onClose={() => {}}
        onReportReady={onReportReady}
        startReport={startReport}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/ticker/i), {
      target: { value: "aapl" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    await waitFor(() =>
      expect(onReportReady).toHaveBeenCalledWith({
        report_id: "r_1",
        title: "AAPL",
      }),
    );
    expect(startReport).toHaveBeenCalledWith({ ticker: "AAPL" });
  });

  it("shows selected company state with last earnings date when ticker matches a watchlist entry", () => {
    render(
      <OnDemandReportModal
        open
        onClose={() => {}}
        onReportReady={() => {}}
        startReport={async () => ({ report_id: "x", title: "t" })}
        entries={[
          {
            id: "e1",
            ticker: "AAPL",
            company_name: "Apple Inc.",
            next_earnings_date: "2026-01-30",
            release_timing: "post_market",
          },
        ]}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/ticker/i), {
      target: { value: "aapl" },
    });
    const block = screen.getByTestId("selected-company");
    expect(block).toHaveTextContent("AAPL");
    expect(block).toHaveTextContent(/Apple Inc/);
    expect(block).toHaveTextContent(/Last earnings/);
    expect(block).toHaveTextContent(/Jan 30, 2026/);
  });

  it("shows error when startReport rejects", async () => {
    const startReport = vi.fn().mockRejectedValue(new Error("boom"));
    render(
      <OnDemandReportModal
        open
        onClose={() => {}}
        onReportReady={() => {}}
        startReport={startReport}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/ticker/i), {
      target: { value: "AAPL" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByText(/failed|boom/i)).toBeInTheDocument();
  });
});
