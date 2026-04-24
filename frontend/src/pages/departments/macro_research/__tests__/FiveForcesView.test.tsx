import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  runAssessment: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => mocks);

import FiveForcesView from "../FiveForcesView";
import { makeResult } from "./fixtures";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });
  mocks.getDashboard.mockResolvedValue(
    makeResult({
      slug: "five_forces",
      display_name: "Five Forces",
      severity: "red",
      tiers: [
        {
          tier: "T3",
          data: {
            force_scores: {
              debt_money: 8,
              political: 7,
              geopolitical: 9,
              technology: 4,
              natural: 2,
            },
            active_force_count: 3,
            bucket: "Elevated",
          },
          errors: [],
          generated_at: null,
        },
        {
          tier: "T4",
          data: { assessment: "Multiple forces firing simultaneously" },
          errors: [],
          generated_at: null,
        },
      ],
    }),
  );
});

describe("FiveForcesView", () => {
  it("renders five force rows", async () => {
    render(<FiveForcesView />);
    await waitFor(() =>
      expect(screen.getByTestId("force-row-debt_money")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("force-row-political")).toBeInTheDocument();
    expect(screen.getByTestId("force-row-geopolitical")).toBeInTheDocument();
    expect(screen.getByTestId("force-row-technology")).toBeInTheDocument();
    expect(screen.getByTestId("force-row-natural")).toBeInTheDocument();
  });

  it("renders active force count banner", async () => {
    render(<FiveForcesView />);
    const panel = await screen.findByTestId("active-force-panel");
    expect(panel.textContent).toMatch(/3/);
    expect(panel.textContent).toMatch(/Elevated/);
  });

  it("run-assessment button calls runAssessment", async () => {
    render(<FiveForcesView />);
    const btn = await screen.findByRole("button", {
      name: /run assessment now/i,
    });
    fireEvent.click(btn);
    await waitFor(() =>
      expect(mocks.runAssessment).toHaveBeenCalledWith("five_forces"),
    );
  });
});
