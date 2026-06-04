import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getConfig: vi.fn(),
  runAssessment: vi.fn(),
  putThresholdOverrides: vi.fn(),
  getSchedule: vi.fn(),
  putSchedule: vi.fn(),
  deleteSchedule: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => apiMocks);

const deptHealthMocks = vi.hoisted(() => ({
  fetchDeptHealth: vi.fn(),
}));

vi.mock("../../../../api/dept-health", () => deptHealthMocks);

import MRSettingsPanel from "../MRSettingsPanel";

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.getConfig.mockResolvedValue({ threshold_overrides: {} });
  apiMocks.runAssessment.mockResolvedValue(null);
  apiMocks.putThresholdOverrides.mockResolvedValue(null);
  apiMocks.getSchedule.mockResolvedValue({ cron_expression: null, last_assessment_at: null });
  apiMocks.putSchedule.mockResolvedValue(null);
  apiMocks.deleteSchedule.mockResolvedValue(null);
  deptHealthMocks.fetchDeptHealth.mockResolvedValue([
    {
      department_id: "macro_research",
      status: "active",
      reason: null,
      missing_categories: [],
      unresolved_needs: [],
      required_categories: ["web_search"],
      optional_categories: ["financial", "news"],
      satisfied_categories: ["web_search"],
    },
  ]);
});

describe("MRSettingsPanel source coverage", () => {
  it("renders source coverage section with correct active/not-configured state", async () => {
    render(
      <MRSettingsPanel
        dashboards={[{ slug: "debt_cycle", display_name: "Debt Cycle" } as any]}
        onClose={() => {}}
      />,
    );

    expect(await screen.findByTestId("mr-coverage")).toBeInTheDocument();
    expect(screen.getByTestId("mr-coverage-web_search")).toHaveTextContent("active");
    expect(screen.getByTestId("mr-coverage-financial")).toHaveTextContent("not configured");
    expect(screen.getByTestId("mr-coverage-financial")).toHaveTextContent("fall back to web search");
  });
});
