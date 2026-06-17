import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  runAssessment: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => apiMocks);

const deptHealthMocks = vi.hoisted(() => ({
  fetchDeptHealth: vi.fn(),
}));

vi.mock("../../../../api/dept-health", () => deptHealthMocks);

import MRSettingsPanel from "../MRSettingsPanel";

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.runAssessment.mockResolvedValue(null);
  deptHealthMocks.fetchDeptHealth.mockResolvedValue([
    {
      department_id: "macro_research",
      status: "active",
      reason: null,
      missing_categories: [],
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
