import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  runAssessment: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => mocks);

import AllWeatherView from "../AllWeatherView";
import { makeResult } from "./fixtures";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getDashboard.mockResolvedValue(
    makeResult({
      slug: "all_weather",
      display_name: "All-Weather",
      severity: "amber",
      tiers: [
        {
          tier: "T3",
          data: {
            portfolio_source: "fallback_60_40",
            portfolio: { stocks: 0.6, bonds: 0.4, gold: 0 },
            reference_allocation: { stocks: 0.3, bonds: 0.55, gold: 0.075, commodities: 0.075 },
            risk_contributions: { stocks: 0.75, bonds: 0.2, gold: 0.025, commodities: 0.025 },
            reference_risk_contributions: { stocks: 0.4, bonds: 0.3, gold: 0.15, commodities: 0.15 },
            season_coverage: { Spring: "green", Summer: "amber", Autumn: "red", Winter: "amber" },
            gold_gap: 0.075,
            overall_coverage_label: "Concentrated",
          },
          errors: [],
          generated_at: null,
        },
        {
          tier: "T4",
          data: { assessment: "Overweight stocks vs All-Weather" },
          errors: [],
          generated_at: null,
        },
      ],
    }),
  );
});

describe("AllWeatherView", () => {
  it("renders fallback banner when portfolio_source is fallback", async () => {
    render(<AllWeatherView />);
    expect(await screen.findByTestId("fallback-banner")).toBeInTheDocument();
  });

  it("renders season coverage cells", async () => {
    render(<AllWeatherView />);
    await waitFor(() =>
      expect(screen.getByText("Spring")).toBeInTheDocument(),
    );
    expect(screen.getByText("Winter")).toBeInTheDocument();
  });

  it("renders gold gap percentage", async () => {
    render(<AllWeatherView />);
    const hits = await screen.findAllByText("7.5%");
    expect(hits.length).toBeGreaterThan(0);
  });
});
