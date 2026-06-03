import { act, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEBT_CYCLE_FALLBACK } from "../../../../lib/macro_research/dalio_copy/debt_cycle";
import { FOUR_SEASONS_FALLBACK } from "../../../../lib/macro_research/dalio_copy/four_seasons";
import { WORLD_ORDER_FALLBACK } from "../../../../lib/macro_research/dalio_copy/world_order";

const apiMocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  runAssessment: vi.fn(),
}));

vi.mock("../../../../api/macro_research", () => apiMocks);

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="echarts-stub" />,
}));

import DebtCycleView from "../DebtCycleView";
import FourSeasonsView from "../FourSeasonsView";
import AllWeatherView from "../AllWeatherView";
import WorldOrderView from "../WorldOrderView";
import FiveForcesView from "../FiveForcesView";
import SummaryView from "../SummaryView";

beforeEach(() => {
  vi.clearAllMocks();
  // Default: live debt_cycle payload (reuse the canonical T1 shape as fixture).
  apiMocks.getDashboard.mockResolvedValue({
    payload: DEBT_CYCLE_FALLBACK,
    generated_at: "2026-06-01T00:00:00Z",
    is_stale: false,
    provenance: "live",
  });
  apiMocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });
});

function inRouter(node: React.ReactNode) {
  return <MemoryRouter>{node}</MemoryRouter>;
}

describe("DebtCycleView", () => {
  it("renders live cache content: scorecard, phase box, watchlist, and synthesis verdict", async () => {
    render(inRouter(<DebtCycleView />));
    expect(
      await screen.findByText(/T1 · US debt cycle position report/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Section A — headline scorecard/i)).toBeInTheDocument();
    expect(screen.getByTestId("t1-scorecard")).toBeInTheDocument();
    expect(screen.getByText(/Govt debt \/ GDP/i)).toBeInTheDocument();
    expect(screen.getByText(/Interest cost \/ federal revenue/i)).toBeInTheDocument();
    expect(screen.getByTestId("t1-phase-box")).toBeInTheDocument();
    expect(screen.getByTestId("t1-watchlist")).toBeInTheDocument();
    expect(screen.getByTestId("t1-verdict")).toBeInTheDocument();
    expect(screen.getByText(/Section D synthesis/i)).toBeInTheDocument();
  });

  it("renders the empty state with no fabricated numbers when payload is null", async () => {
    apiMocks.getDashboard.mockResolvedValueOnce({
      payload: null,
      generated_at: null,
      is_stale: false,
      provenance: null,
    });
    render(inRouter(<DebtCycleView />));
    expect(
      await screen.findByText(/hasn.t been generated yet/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("mr-dash-empty-generate")).toBeInTheDocument();
    // No live content, and no fabricated reading rendered.
    expect(screen.queryByTestId("t1-scorecard")).not.toBeInTheDocument();
    expect(screen.queryByText(/125\.2%/)).not.toBeInTheDocument();
  });

  it("polls until the payload lands and shows live content (poll-to-live)", async () => {
    vi.useFakeTimers();
    const POLL_INTERVAL_MS = 6000;
    try {
      // Initial load → empty; all subsequent calls → live payload.
      apiMocks.getDashboard
        .mockResolvedValueOnce({
          payload: null,
          generated_at: null,
          is_stale: false,
          provenance: null,
        })
        .mockResolvedValue({
          payload: DEBT_CYCLE_FALLBACK,
          generated_at: "2026-06-01T00:00:00Z",
          is_stale: false,
          provenance: "live",
        });
      apiMocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });

      render(inRouter(<DebtCycleView />));

      // Flush the initial getDashboard microtask so the component settles to empty state.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      const btn = screen.getByTestId("mr-dash-empty-generate");

      // Click; button should immediately show "Generating…" and be disabled.
      act(() => {
        btn.click();
      });

      // Flush the runAssessment promise.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      // Still in generating state — live content must NOT be shown yet.
      expect(screen.getByTestId("mr-dash-empty-generate")).toBeDisabled();
      expect(screen.queryByText(/T1 · US debt cycle position report/i)).not.toBeInTheDocument();

      // Advance one poll interval — getDashboard resolves with live payload.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
      });

      // Live content now rendered.
      expect(screen.getByText(/T1 · US debt cycle position report/i)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows scheduler-unavailable note when runAssessment returns cancelled", async () => {
    vi.useFakeTimers();
    try {
      apiMocks.getDashboard.mockResolvedValue({
        payload: null,
        generated_at: null,
        is_stale: false,
        provenance: null,
      });
      apiMocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "cancelled" });

      render(inRouter(<DebtCycleView />));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      const btn = screen.getByTestId("mr-dash-empty-generate");

      act(() => {
        btn.click();
      });

      // Flush the runAssessment promise.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      // Scheduler unavailable note shown, still on empty state.
      expect(screen.getByTestId("mr-dash-empty-note")).toBeInTheDocument();
      expect(screen.getByTestId("mr-dash-empty-note").textContent).toMatch(
        /scheduler unavailable/i,
      );
      expect(screen.queryByText(/T1 · US debt cycle position report/i)).not.toBeInTheDocument();

      // No further polling — advance well past the poll interval; content stays null.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
      expect(screen.queryByText(/T1 · US debt cycle position report/i)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("FourSeasonsView", () => {
  it("renders live cache content: scorecard, quadrant map, transition risk, and asset playbook", async () => {
    apiMocks.getDashboard.mockResolvedValue({
      payload: FOUR_SEASONS_FALLBACK,
      generated_at: "2026-06-01T00:00:00Z",
      is_stale: false,
      provenance: "live",
    });
    render(inRouter(<FourSeasonsView />));
    expect(
      await screen.findByText(/T2 · Four-seasons diagnostic — US/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Section A — quadrant inputs/i)).toBeInTheDocument();
    expect(screen.getByTestId("t2-scorecard")).toBeInTheDocument();
    expect(screen.getAllByText(/Manufacturing PMI/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Real GDP \(annualised\)/i)).toBeInTheDocument();
    expect(screen.getByTestId("t2-quadrant-map")).toBeInTheDocument();
    expect(screen.getByTestId("t2-quadrant-marker-now")).toBeInTheDocument();
    expect(screen.getByTestId("t2-quadrant-marker-prev")).toBeInTheDocument();
    expect(screen.getByTestId("t2-verdict")).toBeInTheDocument();
    expect(screen.getByTestId("t2-transition-risk")).toBeInTheDocument();
    expect(screen.getByTestId("t2-asset-playbook")).toBeInTheDocument();
    expect(screen.getByText(/Section D — asset playbook/i)).toBeInTheDocument();
  });

  it("renders the empty state when payload is null", async () => {
    apiMocks.getDashboard.mockResolvedValueOnce({
      payload: null,
      generated_at: null,
      is_stale: false,
      provenance: null,
    });
    render(inRouter(<FourSeasonsView />));
    expect(
      await screen.findByText(/hasn.t been generated yet/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("mr-dash-empty-generate")).toBeInTheDocument();
    expect(screen.queryByTestId("t2-scorecard")).not.toBeInTheDocument();
  });

  it("polls until the payload lands and shows live content (poll-to-live)", async () => {
    vi.useFakeTimers();
    const POLL_INTERVAL_MS = 6000;
    try {
      apiMocks.getDashboard
        .mockResolvedValueOnce({
          payload: null,
          generated_at: null,
          is_stale: false,
          provenance: null,
        })
        .mockResolvedValue({
          payload: FOUR_SEASONS_FALLBACK,
          generated_at: "2026-06-01T00:00:00Z",
          is_stale: false,
          provenance: "live",
        });
      apiMocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });

      render(inRouter(<FourSeasonsView />));

      // Flush the initial getDashboard microtask so the component settles to empty state.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      const btn = screen.getByTestId("mr-dash-empty-generate");

      act(() => {
        btn.click();
      });

      // Flush the runAssessment promise.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      // Still generating — live content must NOT be shown yet.
      expect(screen.getByTestId("mr-dash-empty-generate")).toBeDisabled();
      expect(screen.queryByTestId("t2-scorecard")).not.toBeInTheDocument();

      // Advance one poll interval — getDashboard resolves with live payload.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
      });

      expect(screen.getByTestId("t2-scorecard")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("AllWeatherView", () => {
  it("renders the comparison donuts, coverage map, risk parity audit, gold check, and caveats", () => {
    render(inRouter(<AllWeatherView />));
    expect(screen.getByText(/T3 · All-Weather allocation audit/i)).toBeInTheDocument();
    expect(screen.getByTestId("t3-comparison")).toBeInTheDocument();
    expect(screen.getByText(/Section A — season coverage map/i)).toBeInTheDocument();
    expect(screen.getByTestId("t3-coverage-map")).toBeInTheDocument();
    expect(screen.getByText(/Autumn \(stagflation\)/i)).toBeInTheDocument();
    expect(screen.getByTestId("t3-risk-parity")).toBeInTheDocument();
    expect(screen.getByTestId("t3-risk-bars-benchmark")).toBeInTheDocument();
    expect(screen.getByTestId("t3-risk-bars-reference")).toBeInTheDocument();
    expect(screen.getByTestId("t3-gold-check")).toBeInTheDocument();
    expect(screen.getByTestId("t3-caveats")).toBeInTheDocument();
    expect(screen.getByTestId("t3-verdict")).toBeInTheDocument();
  });
});

describe("WorldOrderView", () => {
  it("renders live cache content: reserve scorecard, empire cycle, analogs, wealth shift, and verdict", async () => {
    apiMocks.getDashboard.mockResolvedValue({
      payload: WORLD_ORDER_FALLBACK,
      generated_at: "2026-06-01T00:00:00Z",
      is_stale: false,
      provenance: "live",
    });
    render(inRouter(<WorldOrderView />));
    expect(
      await screen.findByText(/T4 · World order assessment/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("t4-scorecard")).toBeInTheDocument();
    expect(screen.getByText(/USD share of global FX reserves/i)).toBeInTheDocument();
    expect(screen.getByTestId("t4-reserve-chart")).toBeInTheDocument();
    expect(screen.getByTestId("t4-stage-strip")).toBeInTheDocument();
    expect(screen.getByTestId("t4-dalio-quote")).toBeInTheDocument();
    expect(screen.getByTestId("t4-stage-markers")).toBeInTheDocument();
    expect(screen.getByTestId("t4-analog-grid")).toBeInTheDocument();
    expect(screen.getByTestId("t4-wealth-shift")).toBeInTheDocument();
    expect(screen.getByTestId("t4-gold-range")).toBeInTheDocument();
    expect(screen.getByTestId("t4-currency-exposure")).toBeInTheDocument();
    expect(screen.getByTestId("t4-sovereign-bond")).toBeInTheDocument();
    expect(screen.getByTestId("t4-verdict")).toBeInTheDocument();
  });

  it("renders the empty state when payload is null", async () => {
    apiMocks.getDashboard.mockResolvedValueOnce({
      payload: null,
      generated_at: null,
      is_stale: false,
      provenance: null,
    });
    render(inRouter(<WorldOrderView />));
    expect(
      await screen.findByText(/hasn.t been generated yet/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("mr-dash-empty-generate")).toBeInTheDocument();
    expect(screen.queryByTestId("t4-scorecard")).not.toBeInTheDocument();
  });

  it("polls until the payload lands and shows live content (poll-to-live)", async () => {
    vi.useFakeTimers();
    const POLL_INTERVAL_MS = 6000;
    try {
      apiMocks.getDashboard
        .mockResolvedValueOnce({
          payload: null,
          generated_at: null,
          is_stale: false,
          provenance: null,
        })
        .mockResolvedValue({
          payload: WORLD_ORDER_FALLBACK,
          generated_at: "2026-06-01T00:00:00Z",
          is_stale: false,
          provenance: "live",
        });
      apiMocks.runAssessment.mockResolvedValue({ job_run_id: "j1", status: "queued" });

      render(inRouter(<WorldOrderView />));

      // Flush the initial getDashboard microtask so the component settles to empty state.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      const btn = screen.getByTestId("mr-dash-empty-generate");

      act(() => {
        btn.click();
      });

      // Flush the runAssessment promise.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      // Still generating — live content must NOT be shown yet.
      expect(screen.getByTestId("mr-dash-empty-generate")).toBeDisabled();
      expect(screen.queryByTestId("t4-scorecard")).not.toBeInTheDocument();

      // Advance one poll interval — getDashboard resolves with live payload.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
      });

      expect(screen.getByTestId("t4-scorecard")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("FiveForcesView", () => {
  it("renders the force scorecard, reinforcement loops, market signals, gold allocation, scenarios, and verdict", () => {
    render(inRouter(<FiveForcesView />));
    expect(screen.getByText(/Five interlocking forces — April 2026/i)).toBeInTheDocument();
    expect(screen.getByTestId("t5-scorecard")).toBeInTheDocument();
    expect(screen.getByText(/Debt & money cycle/i)).toBeInTheDocument();
    expect(screen.getByText(/Geopolitical cycle/i)).toBeInTheDocument();
    expect(screen.getByText(/Technology wave/i)).toBeInTheDocument();
    expect(screen.getByTestId("t5-loops")).toBeInTheDocument();
    expect(screen.getByTestId("t5-active-count")).toBeInTheDocument();
    expect(screen.getByTestId("t5-signals")).toBeInTheDocument();
    expect(screen.getByTestId("t5-gold-allocation")).toBeInTheDocument();
    expect(screen.getByTestId("t5-scenarios")).toBeInTheDocument();
    expect(screen.getByTestId("t5-verdict")).toBeInTheDocument();
  });
});

describe("SummaryView", () => {
  it("renders the hero with LIA take, regime bar, framework grid, dep map, cascade and consolidated watchlist", () => {
    render(inRouter(<SummaryView />));
    expect(screen.getByText(/Three forces critical/i)).toBeInTheDocument();
    expect(screen.getByTestId("summary-lia-take")).toBeInTheDocument();
    expect(screen.getByTestId("summary-regime-bar")).toBeInTheDocument();
    const grid = screen.getByTestId("summary-framework-grid");
    const t1Card = within(grid).getByText(/Debt & Money Cycle/i).closest("a");
    expect(t1Card?.getAttribute("href")).toBe("/macro-research/debt_cycle");
    const t5Card = within(grid).getByText(/Five Forces/i).closest("a");
    expect(t5Card?.getAttribute("href")).toBe("/macro-research/five_forces");
    expect(screen.getByTestId("summary-dep-map")).toBeInTheDocument();
    expect(screen.getByTestId("summary-cascade")).toBeInTheDocument();
    expect(screen.getByTestId("summary-watchlist")).toBeInTheDocument();
    expect(screen.getByText(/Cross-framework dependency map/i)).toBeInTheDocument();
    expect(screen.getByText(/Gold thesis · cross-framework cascade/i)).toBeInTheDocument();
  });
});
