import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  listDashboards: vi.fn(),
  getDashboard: vi.fn(),
  runAssessment: vi.fn(),
  getConfig: vi.fn(),
  putThresholdOverrides: vi.fn(),
  getSchedule: vi.fn(),
  putSchedule: vi.fn(),
  deleteSchedule: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => apiMocks);

const deptHealthMocks = vi.hoisted(() => ({
  fetchDeptHealth: vi.fn(),
  recheckDeptHealth: vi.fn(),
}));

vi.mock("../../../../api/dept-health", () => deptHealthMocks);

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="echarts-stub" />,
}));

import MacroResearch from "../../MacroResearch";

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.listDashboards.mockResolvedValue({
    dashboards: [
      { slug: "debt_cycle", display_name: "Debt Cycle" },
      { slug: "four_seasons", display_name: "Four Seasons" },
      { slug: "all_weather", display_name: "All-Weather" },
      { slug: "world_order", display_name: "World Order" },
      { slug: "five_forces", display_name: "Five Forces" },
      { slug: "summary", display_name: "Summary" },
    ],
  });
  apiMocks.getDashboard.mockResolvedValue({
    payload: null,
    generated_at: null,
    is_stale: false,
    provenance: null,
  });
  apiMocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });
  apiMocks.getConfig.mockResolvedValue({ view_config: {}, threshold_overrides: {} });
  apiMocks.getSchedule.mockResolvedValue({ cron_expression: null, last_assessment_at: null });
  deptHealthMocks.fetchDeptHealth.mockResolvedValue([]);
});

function renderShell(initialPath = "/macro-research") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <MacroResearch />
    </MemoryRouter>,
  );
}

describe("MacroResearch shell", () => {
  it("renders title, live pill, and the five framework tabs", () => {
    renderShell();
    expect(screen.getByText("Macro Research")).toBeInTheDocument();
    expect(screen.getByTestId("mr-live-pill")).toBeInTheDocument();
    expect(screen.getByText("Summary")).toBeInTheDocument();
    expect(screen.getByText("Debt Cycle")).toBeInTheDocument();
    expect(screen.getByText("Four Seasons")).toBeInTheDocument();
    expect(screen.getByText("All-Weather")).toBeInTheDocument();
    expect(screen.getByText("World Order")).toBeInTheDocument();
    expect(screen.getByText("Five Forces")).toBeInTheDocument();
  });

  it("renders T1–T5 tcode chips on tabs", () => {
    renderShell();
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.getByText("T5")).toBeInTheDocument();
  });

  it("opens the settings drawer and offers Run Now for every framework dashboard", () => {
    renderShell();
    fireEvent.click(screen.getByTestId("mr-settings-button"));
    expect(screen.getByTestId("mr-settings-panel")).toBeInTheDocument();
    // All five framework dashboards are now engine-implemented and runnable.
    // (Summary is refreshed from its own overview tab, not this list.)
    for (const slug of [
      "debt_cycle",
      "world_order",
      "four_seasons",
      "all_weather",
      "five_forces",
    ]) {
      expect(screen.getByTestId(`mr-runnow-${slug}`)).toBeInTheDocument();
    }
  });

  it("refresh-cadence select offers once per week, once per month, auto refresh", () => {
    renderShell();
    const select = screen.getByTestId("mr-refresh-select") as HTMLSelectElement;
    const labels = Array.from(select.options).map((o) => o.text);
    expect(labels).toEqual([
      "Once per week",
      "Once per month",
      "Auto refresh",
    ]);
  });

  it("defaults to auto refresh when no schedule is set", async () => {
    apiMocks.getSchedule.mockResolvedValue({
      cron_expression: null,
      last_assessment_at: null,
    });
    renderShell();
    const select = await screen.findByTestId<HTMLSelectElement>("mr-refresh-select");
    await waitFor(() => expect(select.value).toBe("auto"));
  });

  it("preselects once per week when a weekly cron is persisted", async () => {
    apiMocks.getSchedule.mockResolvedValue({
      cron_expression: "0 0 * * 0",
      last_assessment_at: null,
    });
    renderShell();
    const select = await screen.findByTestId<HTMLSelectElement>("mr-refresh-select");
    await waitFor(() => expect(select.value).toBe("weekly"));
  });

  it("writes a weekly cron when once per week is chosen", async () => {
    apiMocks.putSchedule.mockResolvedValue({ cron_expression: "0 0 * * 0" });
    renderShell();
    const select = await screen.findByTestId<HTMLSelectElement>("mr-refresh-select");
    fireEvent.change(select, { target: { value: "weekly" } });
    await waitFor(() =>
      expect(apiMocks.putSchedule).toHaveBeenCalledWith("0 0 * * 0"),
    );
  });

  it("writes a monthly cron when once per month is chosen", async () => {
    apiMocks.putSchedule.mockResolvedValue({ cron_expression: "0 0 1 * *" });
    renderShell();
    const select = await screen.findByTestId<HTMLSelectElement>("mr-refresh-select");
    fireEvent.change(select, { target: { value: "monthly" } });
    await waitFor(() =>
      expect(apiMocks.putSchedule).toHaveBeenCalledWith("0 0 1 * *"),
    );
  });

  it("clears the schedule when auto refresh is chosen", async () => {
    apiMocks.getSchedule.mockResolvedValue({
      cron_expression: "0 0 * * 0",
      last_assessment_at: null,
    });
    apiMocks.deleteSchedule.mockResolvedValue(null);
    renderShell();
    const select = await screen.findByTestId<HTMLSelectElement>("mr-refresh-select");
    await waitFor(() => expect(select.value).toBe("weekly"));
    fireEvent.change(select, { target: { value: "auto" } });
    await waitFor(() => expect(apiMocks.deleteSchedule).toHaveBeenCalled());
  });
});
