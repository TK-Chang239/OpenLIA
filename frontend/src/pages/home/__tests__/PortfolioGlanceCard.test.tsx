import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PortfolioGlanceCard } from "../PortfolioGlanceCard";
import * as portfolioApi from "../../../api/portfolio";
import type {
  AnalyticsResponse,
  ValueSeriesResponse,
} from "../../../api/portfolio";

vi.mock("../../../api/portfolio", () => ({
  fetchAnalytics: vi.fn(),
  fetchValueSeries: vi.fn(),
}));

const mocked = portfolioApi as unknown as {
  fetchAnalytics: ReturnType<typeof vi.fn>;
  fetchValueSeries: ReturnType<typeof vi.fn>;
};

function analytics(overrides: Partial<AnalyticsResponse> = {}): AnalyticsResponse {
  return {
    total_market_value: "2184920.18",
    total_cost_basis: "2000000",
    total_unrealized_pl: "184920.18",
    total_unrealized_pl_pct: "9.25",
    display_currency: "USD",
    fx_unavailable: false,
    allocations: {},
    positions: [
      {
        holding_id: "h1",
        ticker: "NVDA",
        shares: "100",
        cost_basis: "500",
        last_price: "900",
        market_value: "90000",
        unrealized_pl: "40000",
        unrealized_pl_pct: "80",
        weight: "0.5",
        currency: "USD",
        previous_close: "880",
        day_change_abs: "2000",
        day_change_pct: "2.27",
      },
    ],
    ...overrides,
  };
}

function series(): ValueSeriesResponse {
  return {
    timeframe: "3m",
    actual_span: { start: "2026-05-09", end: "2026-08-09" },
    points: [
      { date: "2026-05-09", value: "2000000", ts: null },
      { date: "2026-06-09", value: "2100000", ts: null },
      { date: "2026-07-09", value: "2150000", ts: null },
      { date: "2026-08-09", value: "2184920.18", ts: null },
    ],
    period_return_abs: "184920.18",
    period_return_pct: "9.25",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.fetchAnalytics.mockResolvedValue(analytics());
  mocked.fetchValueSeries.mockResolvedValue(series());
});

const renderCard = () =>
  render(
    <MemoryRouter>
      <PortfolioGlanceCard />
    </MemoryRouter>,
  );

describe("PortfolioGlanceCard", () => {
  it("renders the real total market value from analytics", async () => {
    renderCard();
    // $2,184,920 (integer) with .18 in the small decimals span.
    expect(await screen.findByText(/2,184,920/)).toBeInTheDocument();
    expect(screen.getByText(".18")).toBeInTheDocument();
  });

  it("renders the today change and positions count", async () => {
    renderCard();
    // +$2,000 day P/L -> positive; percent computed against prior value.
    expect(await screen.findByText(/today/i)).toHaveTextContent(/\+\$2,000/);
    expect(screen.getByText(/1 Positions/i)).toBeInTheDocument();
  });

  it("draws a chart path from the value series", async () => {
    const { container } = renderCard();
    await waitFor(() => expect(mocked.fetchValueSeries).toHaveBeenCalled());
    await waitFor(() => {
      // The line path starts with M and has multiple L segments from real points.
      const paths = Array.from(container.querySelectorAll("path")).map((p) =>
        p.getAttribute("d"),
      );
      expect(paths.some((d) => d && d.startsWith("M") && d.includes("L"))).toBe(
        true,
      );
    });
  });

  it("shows an empty state when there are no holdings", async () => {
    mocked.fetchAnalytics.mockResolvedValue(
      analytics({ total_market_value: "0", positions: [] }),
    );
    renderCard();
    expect(await screen.findByText(/no holdings yet/i)).toBeInTheDocument();
  });
});
