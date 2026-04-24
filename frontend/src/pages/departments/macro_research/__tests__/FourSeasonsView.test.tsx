import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  runAssessment: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => mocks);

import FourSeasonsView from "../FourSeasonsView";
import { makeResult } from "./fixtures";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getDashboard.mockResolvedValue(
    makeResult({
      slug: "four_seasons",
      display_name: "Four Seasons",
      severity: "green",
      tiers: [
        {
          tier: "T3",
          data: {
            season: "Spring",
            confidence: "clear",
            growth_axis: "rising",
            inflation_axis: "falling",
            credit_spread: 0.04,
            asset_playbook: { best: ["equities"], worst: ["commodities"] },
          },
          errors: [],
          generated_at: null,
        },
        {
          tier: "T4",
          data: { assessment: "Regime is supportive of equities" },
          errors: [],
          generated_at: null,
        },
      ],
    }),
  );
});

describe("FourSeasonsView", () => {
  it("renders season + playbook", async () => {
    render(<FourSeasonsView />);
    expect(await screen.findByText("Spring")).toBeInTheDocument();
    expect(screen.getByText("equities")).toBeInTheDocument();
    expect(screen.getByText("commodities")).toBeInTheDocument();
  });

  it("shows smart-mode toggle", async () => {
    render(<FourSeasonsView />);
    await waitFor(() =>
      expect(
        screen.getByRole("switch", { name: /smart mode/i }),
      ).toBeInTheDocument(),
    );
  });
});
