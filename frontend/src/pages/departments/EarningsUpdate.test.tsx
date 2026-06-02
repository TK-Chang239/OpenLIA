import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/earnings-update";
import * as settingsApi from "../../api/settings";
import * as viewer from "../../components/viewer/FileViewerContext";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";
import EarningsUpdate from "./EarningsUpdate";

vi.mock("../../components/earnings-update/calendar/EuCalendar", () => ({
  EuCalendar: () => <div data-testid="eu-cal-month" />,
}));

vi.mock("../../components/earnings-update/OnDemandReportModal", () => ({
  OnDemandReportModal: ({ open }: { open: boolean }) =>
    open ? <div data-testid="on-demand-modal-open" /> : null,
}));

const baseSettings: api.EuSettings = {
  provider_kind: "anthropic",
  model: "claude-sonnet-4-6",
  template_id: "eu_default",
  language: "en",
  length: "normal",
  reasoning_effort: null,
  enabled_provider_ids: ["eodhd"],
  web_search_enabled: false,
  instructions_id: null,
  batch_enabled: false,
};

function makeRun(over: Partial<api.RunSummary>): api.RunSummary {
  return {
    report_id: "r1",
    ticker: "AAPL",
    subject: "Apple beats on Services",
    template_id: "eu_default",
    trigger_kind: "on_demand",
    fiscal_date: null,
    language: "en",
    length: "normal",
    status: "completed",
    created_at: new Date().toISOString(),
    completed_at: null,
    reasoning_effort: null,
    ...over,
  };
}

function makeSchedule(
  over: Partial<api.EuScheduleEntry>,
): api.EuScheduleEntry {
  return {
    id: "s1",
    ticker: "MSFT.US",
    fiscal_date: "2099-06-15",
    release_timing: "post_market",
    eps_estimate: null,
    revenue_estimate: null,
    scheduled_run_at: "2099-06-15T23:00:00Z",
    status: "pending",
    attempts: 0,
    report_id: null,
    ...over,
  };
}

function renderPage() {
  return render(
    <FileViewerProvider>
      <EarningsUpdate />
    </FileViewerProvider>,
  );
}

describe("EarningsUpdatePage (v2)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "fetchRuns").mockResolvedValue([]);
    vi.spyOn(api, "fetchSettings").mockResolvedValue(baseSettings);
    vi.spyOn(api, "fetchSchedule").mockResolvedValue({ schedule: [] });
    vi.spyOn(api, "fetchTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  it("renders topbar with Watchlist and Settings buttons", async () => {
    renderPage();
    expect(
      await screen.findByRole("button", { name: /watchlist/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /report settings/i }),
    ).toBeInTheDocument();
  });

  it("shows full-page empty state when watchlist + runs are empty", async () => {
    renderPage();
    expect(await screen.findByTestId("eu-empty-page")).toBeInTheDocument();
  });

  it("renders the feed when runs exist", async () => {
    vi.spyOn(api, "fetchRuns").mockResolvedValue([makeRun({})]);
    renderPage();
    expect(
      await screen.findByText(/Apple beats on Services/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Earlier this week")).toBeInTheDocument();
  });

  it("renders schedule rows in the Up Next section", async () => {
    vi.spyOn(api, "fetchRuns").mockResolvedValue([makeRun({})]);
    vi.spyOn(api, "fetchSchedule").mockResolvedValue({
      schedule: [makeSchedule({ ticker: "MSFT.US" })],
    });
    renderPage();
    expect(await screen.findByText(/MSFT.US/)).toBeInTheDocument();
  });

  it("opens a report via fileViewer with the eu_v2_report source and report_id", async () => {
    const openSpy = vi.fn();
    vi.spyOn(viewer, "useFileViewer").mockReturnValue({
      current: null,
      lastTrigger: null,
      open: openSpy,
      close: vi.fn(),
    } as unknown as ReturnType<typeof viewer.useFileViewer>);
    vi.spyOn(api, "fetchRuns").mockResolvedValue([
      makeRun({ report_id: "rX", ticker: "AAPL", subject: "Apple beats" }),
    ]);
    renderPage();
    const open = await screen.findByText(/open update/i);
    fireEvent.click(open);
    await waitFor(() => expect(openSpy).toHaveBeenCalled());
    expect(openSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "report",
        source: { kind: "eu_v2_report", reportId: "rX" },
      }),
    );
  });

  it("shows the disabled banner when the engine returns 503", async () => {
    vi.spyOn(api, "fetchRuns").mockRejectedValue(new Error("503 disabled"));
    vi.spyOn(api, "fetchSettings").mockRejectedValue(new Error("503 disabled"));
    renderPage();
    expect(
      await screen.findByTestId("eu-v2-disabled-banner"),
    ).toBeInTheDocument();
  });

  it("shows the Generate report button and opens the on-demand modal", async () => {
    renderPage();
    const btn = await screen.findByRole("button", { name: /generate report/i });
    fireEvent.click(btn);
    expect(screen.getByTestId("on-demand-modal-open")).toBeInTheDocument();
  });

  it("switches to the calendar view via the toggle", async () => {
    vi.spyOn(api, "fetchRuns").mockResolvedValue([makeRun({})]);
    renderPage();
    fireEvent.click(await screen.findByRole("tab", { name: /calendar/i }));
    expect(screen.getByTestId("eu-cal-month")).toBeInTheDocument();
  });

  it("no longer renders the segmented report filter", async () => {
    vi.spyOn(api, "fetchRuns").mockResolvedValue([makeRun({})]);
    renderPage();
    await screen.findByRole("tab", { name: /stream/i });
    // Only the two view-toggle tabs (Stream + Calendar) remain — the old
    // All/Watchlist/Portfolio/Beats/Misses segmented filter is gone.
    expect(screen.getAllByRole("tab")).toHaveLength(2);
    expect(
      screen.queryByRole("tab", { name: /^watchlist$/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /beats/i })).not.toBeInTheDocument();
  });

  it("deletes a feed report after confirming", async () => {
    vi.spyOn(api, "fetchRuns").mockResolvedValue([
      makeRun({ report_id: "rDel", subject: "Apple delete me" }),
    ]);
    const del = vi.spyOn(api, "deleteRun").mockResolvedValue(undefined);
    renderPage();
    // The single recent run renders as the hero EuBigCard; click its trash.
    fireEvent.click(
      await screen.findByRole("button", { name: /remove report/i }),
    );
    // Confirm dialog: the confirm button label is exactly "Remove".
    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("rDel"));
  });
});
