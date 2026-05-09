import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
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
  apiMocks.getDashboard.mockResolvedValue({
    slug: "debt_cycle",
    display_name: "Debt Cycle",
    severity: "amber",
    tiers: [],
    headline: null,
    generated_at: new Date().toISOString(),
    smart_mode_active: false,
  });
});

function inRouter(node: React.ReactNode) {
  return <MemoryRouter>{node}</MemoryRouter>;
}

describe("DebtCycleView", () => {
  it("renders the headline scorecard, phase box, watchlist, and synthesis verdict", () => {
    render(inRouter(<DebtCycleView />));
    expect(screen.getByText(/T1 · US debt cycle position report/i)).toBeInTheDocument();
    expect(screen.getByText(/Section A — headline scorecard/i)).toBeInTheDocument();
    expect(screen.getByTestId("t1-scorecard")).toBeInTheDocument();
    expect(screen.getByText(/Govt debt \/ GDP/i)).toBeInTheDocument();
    expect(screen.getByText(/Interest cost \/ federal revenue/i)).toBeInTheDocument();
    expect(screen.getByTestId("t1-phase-box")).toBeInTheDocument();
    expect(screen.getByTestId("t1-watchlist")).toBeInTheDocument();
    expect(screen.getByTestId("t1-verdict")).toBeInTheDocument();
    expect(screen.getByText(/Section D synthesis/i)).toBeInTheDocument();
  });
});

describe("FourSeasonsView", () => {
  it("renders the scorecard, quadrant map, transition risk, and asset playbook", () => {
    render(inRouter(<FourSeasonsView />));
    expect(screen.getByText(/T2 · Four-seasons diagnostic — US/i)).toBeInTheDocument();
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
  it("renders the reserve scorecard, empire cycle, analogs, wealth shift, and verdict", () => {
    render(inRouter(<WorldOrderView />));
    expect(screen.getByText(/T4 · World order assessment/i)).toBeInTheDocument();
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
