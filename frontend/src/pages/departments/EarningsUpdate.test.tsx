import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/earnings-update";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";
import EarningsUpdate from "./EarningsUpdate";

function renderPage() {
  return render(
    <FileViewerProvider>
      <EarningsUpdate />
    </FileViewerProvider>,
  );
}

describe("EarningsUpdatePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "fetchRecentReports").mockResolvedValue({ reports: [] });
    vi.spyOn(api, "fetchConfig").mockResolvedValue({
      report_length: "normal",
      enabled_section_ids: [],
      custom_sections: [],
    });
  });

  it("renders topbar with Coverage and Settings buttons", async () => {
    renderPage();
    expect(
      await screen.findByRole("button", { name: /coverage/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /report settings/i }),
    ).toBeInTheDocument();
  });

  it("shows full-page empty state when watchlist + reports are empty", async () => {
    renderPage();
    expect(await screen.findByTestId("eu-empty-page")).toBeInTheDocument();
  });

  it("opens Coverage modal from topbar button", async () => {
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: /^coverage$/i }),
    );
    expect(
      await screen.findByRole("dialog", { name: /coverage/i }),
    ).toBeInTheDocument();
  });

  it("renders feed sections when reports exist", async () => {
    vi.spyOn(api, "fetchRecentReports").mockResolvedValue({
      reports: [
        {
          id: "r1",
          title: "Apple beats on Services",
          subject: "AAPL",
          report_type: "earnings_analysis",
          created_at: new Date().toISOString(),
        },
      ],
    });
    renderPage();
    expect(await screen.findByText(/Today's/i)).toBeInTheDocument();
    expect(screen.getByText("Earlier this week")).toBeInTheDocument();
    expect(
      await screen.findByText(/Apple beats on Services/i),
    ).toBeInTheDocument();
  });

  it("opens on-demand modal from filter strip Ad-hoc button", async () => {
    vi.spyOn(api, "fetchRecentReports").mockResolvedValue({
      reports: [
        {
          id: "r1",
          title: "Existing report",
          subject: "AAPL",
          report_type: "earnings_analysis",
          created_at: new Date().toISOString(),
        },
      ],
    });
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: /generate ad-hoc report/i }),
    );
    expect(
      await screen.findByText(/On-Demand Earnings Update/),
    ).toBeInTheDocument();
  });

  it("shows live big-card while on-demand stream is active", async () => {
    vi.spyOn(api, "fetchRecentReports").mockResolvedValue({
      reports: [
        {
          id: "seed",
          title: "Seed",
          subject: "MSFT",
          report_type: "earnings_analysis",
          created_at: new Date().toISOString(),
        },
      ],
    });
    let resolveStream: (
      v: { report_id: string; title: string },
    ) => void = () => {};
    const startSpy = vi
      .spyOn(api, "startOnDemandReport")
      .mockImplementation(
        () =>
          new Promise<{ report_id: string; title: string }>((resolve) => {
            resolveStream = resolve;
          }),
      );
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: /generate ad-hoc report/i }),
    );
    fireEvent.change(
      await screen.findByPlaceholderText(/ticker symbol/i),
      { target: { value: "AAPL" } },
    );
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByTestId("eu-big-card")).toBeInTheDocument();
    await act(async () => {
      resolveStream({ report_id: "r1", title: "AAPL Earnings" });
    });
    await waitFor(() =>
      expect(screen.getByText(/AAPL Earnings/i)).toBeInTheDocument(),
    );
    expect(startSpy).toHaveBeenCalledWith({ ticker: "AAPL" });
  });

  it("renders error banner with retry when fetch fails", async () => {
    vi.spyOn(api, "fetchWatchlist").mockRejectedValue(new Error("boom"));
    renderPage();
    const banner = await screen.findByRole("alert");
    expect(banner.textContent).toMatch(/Failed to load earnings data/i);

    const fetchSpy = vi.spyOn(api, "fetchWatchlist").mockResolvedValue({
      entries: [],
    });
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
  });
});
