import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/morning-briefing";
import * as settingsApi from "../../api/settings";
import * as viewer from "../../components/viewer/FileViewerContext";
import { FileViewerProvider } from "../../components/viewer/FileViewerContext";
import MorningBriefing from "./MorningBriefing";

function makeRun(over: Partial<api.MbRunSummary>): api.MbRunSummary {
  return {
    report_id: "r1",
    subject: "Markets open higher on rate-cut hopes",
    trigger_kind: "on_demand",
    schedule_id: null,
    template_id: "freeform",
    instructions_id: null,
    language: "en",
    length: "normal",
    status: "completed",
    created_at: new Date().toISOString(),
    completed_at: null,
    reasoning_effort: null,
    highlights: null,
    ...over,
  };
}

function makeSchedule(over: Partial<api.MbSchedule>): api.MbSchedule {
  return {
    id: "s1",
    time: "07:00",
    timezone: "America/New_York",
    days_of_week: ["mon", "tue", "wed", "thu", "fri"],
    label: "Pre-Market",
    is_enabled: true,
    template_id: "freeform",
    instructions_id: null,
    enabled_connectors: { provider_ids: [], web_search: false },
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
    web_search: false,
    ...over,
  };
}

function renderPage() {
  return render(
    <FileViewerProvider>
      <MorningBriefing />
    </FileViewerProvider>,
  );
}

describe("MorningBriefing page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listMbRuns").mockResolvedValue([]);
    vi.spyOn(api, "listMbSchedules").mockResolvedValue([]);
    vi.spyOn(api, "listMbTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(api, "listMbInstructions").mockResolvedValue([]);
    vi.spyOn(api, "getMbDataSources").mockResolvedValue({ sources: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  it("renders the topbar with Schedules, Library, and Run now", async () => {
    renderPage();
    expect(
      await screen.findByRole("button", { name: /schedules/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^library$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /run now/i }),
    ).toBeInTheDocument();
  });

  it("shows the empty state when there are no briefings", async () => {
    renderPage();
    expect(await screen.findByTestId("mb-empty-page")).toBeInTheDocument();
  });

  it("renders the feed when runs exist", async () => {
    vi.spyOn(api, "listMbRuns").mockResolvedValue([
      makeRun({ subject: "Markets open higher on rate-cut hopes" }),
    ]);
    renderPage();
    expect(
      await screen.findByText(/Markets open higher on rate-cut hopes/i),
    ).toBeInTheDocument();
    expect(screen.getByText("This week")).toBeInTheDocument();
  });

  it("opens a briefing via fileViewer with the mb_report source", async () => {
    const openSpy = vi.fn();
    vi.spyOn(viewer, "useFileViewer").mockReturnValue({
      current: null,
      lastTrigger: null,
      open: openSpy,
      close: vi.fn(),
    } as unknown as ReturnType<typeof viewer.useFileViewer>);
    vi.spyOn(api, "listMbRuns").mockResolvedValue([
      makeRun({ report_id: "rX", subject: "Briefing X" }),
    ]);
    renderPage();
    const open = await screen.findByText(/open briefing/i);
    fireEvent.click(open);
    await waitFor(() => expect(openSpy).toHaveBeenCalled());
    expect(openSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "report",
        source: { kind: "mb_report", reportId: "rX" },
      }),
    );
  });

  it("opens the Run now modal", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /run now/i }));
    expect(await screen.findByTestId("mb-run-now-start")).toBeInTheDocument();
  });

  it("opens the schedules view and the schedule editor", async () => {
    vi.spyOn(api, "listMbSchedules").mockResolvedValue([
      makeSchedule({ label: "Pre-Market" }),
    ]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /schedules/i }));
    expect(await screen.findByTestId("mb-schedules")).toBeInTheDocument();
    // Open the editor for the existing row.
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(await screen.findByTestId("mb-schedule-save")).toBeInTheDocument();
    // The timing controls are present (binding + scheduling fields).
    expect(screen.getByTestId("mb-schedule-time")).toBeInTheDocument();
    expect(screen.getByTestId("mb-template-select")).toBeInTheDocument();
  });

  it("opens the Library (cabinet) view", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /^library$/i }));
    expect(await screen.findByTestId("mb-cabinet")).toBeInTheDocument();
  });

  it("deletes a feed briefing after confirming", async () => {
    vi.spyOn(api, "listMbRuns").mockResolvedValue([
      makeRun({ report_id: "rDel", subject: "Delete me" }),
    ]);
    const del = vi.spyOn(api, "deleteMbRun").mockResolvedValue(undefined);
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: /remove briefing/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("rDel"));
  });
});
