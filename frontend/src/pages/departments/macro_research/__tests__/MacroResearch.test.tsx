import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MacroResearch from "../../MacroResearch";

vi.mock("../../../../api/macro_research", () => ({
  listDashboards: vi.fn().mockResolvedValue({
    dashboards: [
      { slug: "debt_cycle", display_name: "Debt Cycle" },
      { slug: "four_seasons", display_name: "Four Seasons" },
      { slug: "all_weather", display_name: "All-Weather" },
      { slug: "world_order", display_name: "World Order" },
      { slug: "five_forces", display_name: "Five Forces" },
    ],
  }),
  getDashboard: vi.fn().mockResolvedValue({
    slug: "debt_cycle",
    display_name: "Debt Cycle",
    severity: "green",
    tiers: [],
    headline: null,
    generated_at: "2026-04-24T00:00:00+00:00",
    smart_mode_active: false,
  }),
  getConfig: vi
    .fn()
    .mockResolvedValue({ view_config: {}, threshold_overrides: {} }),
  putConfig: vi.fn(),
  putThresholdOverrides: vi.fn(),
  runAssessment: vi.fn(),
  getSchedule: vi.fn().mockResolvedValue({ cron_expression: null }),
  putSchedule: vi.fn(),
  deleteSchedule: vi.fn(),
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/macro-research/*" element={<MacroResearch />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MacroResearch shell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders tab bar with Summary + five dashboards", async () => {
    renderAt("/macro-research");
    await screen.findByText("Summary");
    const nav = screen.getByRole("navigation");
    expect(nav).toHaveTextContent("Summary");
    expect(nav).toHaveTextContent("Debt Cycle");
    expect(nav).toHaveTextContent("Four Seasons");
    expect(nav).toHaveTextContent("All-Weather");
    expect(nav).toHaveTextContent("World Order");
    expect(nav).toHaveTextContent("Five Forces");
  });

  it("summary view lists dashboard cards", async () => {
    renderAt("/macro-research");
    await waitFor(() =>
      expect(screen.getByTestId("mr-summary-view")).toBeInTheDocument(),
    );
    // cards linked from SummaryView render display names
    const summary = screen.getByTestId("mr-summary-view");
    expect(summary.textContent).toMatch(/Debt Cycle/);
    expect(summary.textContent).toMatch(/Five Forces/);
  });

  it("opens MR Settings panel from the Settings button (NEW-19-01)", async () => {
    renderAt("/macro-research");
    const btn = await screen.findByTestId("mr-settings-button");
    fireEvent.click(btn);
    expect(await screen.findByTestId("mr-settings-panel")).toBeInTheDocument();
    expect(
      screen.getByTestId("mr-settings-threshold-section"),
    ).toBeInTheDocument();
  });

  it("renders the auto-refresh interval dropdown (NEW-19-02)", async () => {
    renderAt("/macro-research");
    const select = await screen.findByTestId("mr-refresh-select");
    expect(select).toBeInTheDocument();
    // Default state: Off (no value selected).
    expect((select as HTMLSelectElement).value).toBe("");
  });
});
