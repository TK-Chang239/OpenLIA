import { fireEvent, render, screen } from "@testing-library/react";
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

  it("opens the settings drawer and only offers Run Now for implemented dashboards", () => {
    renderShell();
    fireEvent.click(screen.getByTestId("mr-settings-button"));
    expect(screen.getByTestId("mr-settings-panel")).toBeInTheDocument();
    // Engine-implemented dashboards are runnable from Run Now.
    expect(screen.getByTestId("mr-runnow-debt_cycle")).toBeInTheDocument();
    expect(screen.getByTestId("mr-runnow-world_order")).toBeInTheDocument();
    expect(screen.getByTestId("mr-runnow-four_seasons")).toBeInTheDocument();
    // Dashboards the engine cannot generate yet are not runnable.
    expect(screen.queryByTestId("mr-runnow-all_weather")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mr-runnow-five_forces")).not.toBeInTheDocument();
  });

  it("auto-refresh select offers the design's three options", () => {
    renderShell();
    const select = screen.getByTestId("mr-refresh-select") as HTMLSelectElement;
    const labels = Array.from(select.options).map((o) => o.text);
    expect(labels).toEqual([
      "Auto-refresh · 5 min",
      "Auto-refresh · 15 min",
      "Auto-refresh · Off",
    ]);
  });
});
