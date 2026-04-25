import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  runAssessment: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => mocks);

import WorldOrderView from "../WorldOrderView";
import { makeResult } from "./fixtures";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });
  mocks.getDashboard.mockResolvedValue(
    makeResult({
      slug: "world_order",
      display_name: "World Order",
      severity: "amber",
      headline: "Mid — Erosion Underway",
      tiers: [
        {
          tier: "T3",
          data: {
            wealth_shift_stage: "mid",
            wealth_shift_components: {
              institutional: 2,
              market: 2,
              geopolitical: 3,
              retail: 1,
            },
          },
          errors: [],
          generated_at: null,
        },
        {
          tier: "T4",
          data: { assessment: "Reserve status under pressure" },
          errors: [],
          generated_at: null,
        },
      ],
    }),
  );
});

describe("WorldOrderView", () => {
  it("renders empire stage label", async () => {
    render(<WorldOrderView />);
    const hits = await screen.findAllByText(/Mid — Erosion Underway/);
    expect(hits.length).toBeGreaterThan(0);
  });

  it("renders wealth shift components", async () => {
    render(<WorldOrderView />);
    const panel = await screen.findByTestId("wealth-shift-panel");
    expect(panel.textContent).toMatch(/Institutional/);
    expect(panel.textContent).toMatch(/Geopolitical/);
  });

  it("run-assessment button calls runAssessment", async () => {
    render(<WorldOrderView />);
    const btn = await screen.findByRole("button", {
      name: /run assessment now/i,
    });
    fireEvent.click(btn);
    await waitFor(() =>
      expect(mocks.runAssessment).toHaveBeenCalledWith("world_order"),
    );
  });

  it("re-fetches with smart_mode=true when the toggle flips (NEW-19-06)", async () => {
    render(<WorldOrderView />);
    await waitFor(() => expect(mocks.getDashboard).toHaveBeenCalled());
    const initialCalls = mocks.getDashboard.mock.calls.length;
    fireEvent.click(screen.getByRole("switch", { name: /smart mode/i }));
    await waitFor(() =>
      expect(mocks.getDashboard.mock.calls.length).toBeGreaterThan(
        initialCalls,
      ),
    );
    const lastCall =
      mocks.getDashboard.mock.calls[mocks.getDashboard.mock.calls.length - 1];
    expect(lastCall[0]).toBe("world_order");
    expect(lastCall[1]).toBe(true);
  });
});
