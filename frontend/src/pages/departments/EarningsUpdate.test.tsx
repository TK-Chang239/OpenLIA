import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
});
