import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  runAssessment: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => mocks);

import DebtCycleView from "../DebtCycleView";
import { makeResult } from "./fixtures";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getDashboard.mockResolvedValue(
    makeResult({
      slug: "debt_cycle",
      display_name: "Debt Cycle",
      severity: "amber",
      headline: "Late Plateau",
      tiers: [
        {
          tier: "T3",
          data: {
            phase: "Late Plateau",
            indicator_statuses: { debt_gdp: "amber", interest_revenue: "green" },
            monetary_space: {
              rate_cut_headroom: 2.0,
              qe_credibility: "amber",
              currency_debasement_risk: "green",
            },
            watchlist_triggers: [
              { name: "TIPS yield crosses zero", status: "green" },
            ],
          },
          errors: [],
          generated_at: null,
        },
        {
          tier: "T4",
          data: { assessment: "Late-plateau risk is rising" },
          errors: [],
          generated_at: null,
        },
      ],
    }),
  );
  mocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });
});

describe("DebtCycleView", () => {
  it("renders phase from T3", async () => {
    render(<DebtCycleView />);
    await waitFor(() =>
      expect(screen.getByText("Late Plateau")).toBeInTheDocument(),
    );
  });

  it("renders T4 assessment", async () => {
    render(<DebtCycleView />);
    expect(
      await screen.findByText(/Late-plateau risk is rising/),
    ).toBeInTheDocument();
  });

  it("shows smart-mode toggle", async () => {
    render(<DebtCycleView />);
    await waitFor(() =>
      expect(screen.getByRole("switch", { name: /smart mode/i })).toBeInTheDocument(),
    );
  });

  it("shows run-assessment button", async () => {
    render(<DebtCycleView />);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /run assessment now/i }),
      ).toBeInTheDocument(),
    );
  });

  it("re-fetches with smart_mode=true when the toggle flips (NEW-19-06)", async () => {
    const { getByRole } = render(<DebtCycleView />);
    await waitFor(() => expect(mocks.getDashboard).toHaveBeenCalled());
    const initialCalls = mocks.getDashboard.mock.calls.length;
    const toggle = getByRole("switch", { name: /smart mode/i });
    toggle.click();
    await waitFor(() =>
      expect(mocks.getDashboard.mock.calls.length).toBeGreaterThan(initialCalls),
    );
    const lastCall =
      mocks.getDashboard.mock.calls[mocks.getDashboard.mock.calls.length - 1];
    expect(lastCall[0]).toBe("debt_cycle");
    expect(lastCall[1]).toBe(true);
  });
});
