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
    vi.spyOn(api, "fetchSchedules").mockResolvedValue({ schedules: [] });
    vi.spyOn(api, "fetchConfig").mockResolvedValue({
      report_length: "normal",
      enabled_section_ids: [],
      custom_sections: [],
    });
  });

  it("renders header + watchlist + reports sections", async () => {
    renderPage();
    expect(screen.getByText(/Earnings Updates/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText(/Watchlist/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Recent Reports/i)).toBeInTheDocument();
    });
  });

  it("opens on-demand modal when header button clicked", async () => {
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: /on-demand report/i }),
    );
    expect(
      await screen.findByText(/On-Demand Earnings Update/),
    ).toBeInTheDocument();
  });

  it("renders loading skeletons while data fetches are pending", async () => {
    vi.spyOn(api, "fetchWatchlist").mockImplementation(
      () => new Promise(() => {}),
    );
    vi.spyOn(api, "fetchRecentReports").mockImplementation(
      () => new Promise(() => {}),
    );
    renderPage();
    expect(screen.getAllByTestId("eu-skeleton").length).toBeGreaterThan(0);
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

  it("shows generating progress block while on-demand stream is active", async () => {
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
      await screen.findByRole("button", { name: /on-demand report/i }),
    );
    fireEvent.change(await screen.findByPlaceholderText(/ticker/i), {
      target: { value: "AAPL" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByTestId("eu-generating")).toBeInTheDocument();
    await act(async () => {
      resolveStream({ report_id: "r1", title: "AAPL Earnings" });
    });
    await waitFor(() =>
      expect(screen.queryByTestId("eu-generating")).toBeNull(),
    );
    expect(startSpy).toHaveBeenCalledWith({ ticker: "AAPL" });
  });

  it("shows watchlist + recent reports empty-state strings", async () => {
    renderPage();
    expect(
      await screen.findByText(
        /Add companies to your watchlist to track upcoming earnings/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /On-Demand reports and automated reports will appear here/i,
      ),
    ).toBeInTheDocument();
  });
});
