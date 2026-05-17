import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
        onRemove={async () => {}}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/search reports/i), {
      target: { value: "tesla" },
    });
    expect(screen.queryByText(/Apple Inc\./)).toBeNull();
    expect(screen.getByText(/Tesla Inc\./)).toBeInTheDocument();
  });

  it("ticker filter narrows results", () => {
    render(
      <EUCabinetView
        reports={reports}
        onBack={() => {}}
        onOpenReport={() => {}}
        onRemove={async () => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /filters/i }));
    fireEvent.change(screen.getByPlaceholderText(/AAPL/), {
      target: { value: "AAPL" },
    });
    expect(screen.queryByText(/Tesla Inc\./)).toBeNull();
    expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
  });

  it("only fires onRemove after Confirm in confirm dialog", async () => {
    const onRemove = vi.fn().mockResolvedValue(undefined);
    render(
      <EUCabinetView
        reports={reports}
        onBack={() => {}}
        onOpenReport={() => {}}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /remove/i })[0]);
    expect(onRemove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("alertdialog");
    const confirmBtn = Array.from(
      dialog.querySelectorAll<HTMLButtonElement>("button"),
    ).find((b) => b.textContent === "Remove");
    expect(confirmBtn).toBeTruthy();
    fireEvent.click(confirmBtn!);
    await waitFor(() => expect(onRemove).toHaveBeenCalledTimes(1));
  });

  it("back button fires", () => {
    const onBack = vi.fn();
    render(
      <EUCabinetView
        reports={reports}
        onBack={onBack}
        onOpenReport={() => {}}
        onRemove={async () => {}}
      />,
    );
    fireEvent.click(screen.getByText(/Back to Earnings Updates/));
    expect(onBack).toHaveBeenCalled();
  });
});
