import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AnalyticsResponse, PositionAnalytic } from "../api/portfolio";
import { KpiBand } from "./KpiBand";

function pos(
  ticker: string,
  currency: string,
  marketValue: string | null,
  unrealizedPl: string | null,
): PositionAnalytic {
  return {
    holding_id: ticker,
    ticker,
    shares: "1",
    cost_basis: "1",
    last_price: marketValue,
    market_value: marketValue,
    unrealized_pl: unrealizedPl,
    unrealized_pl_pct: null,
    weight: null,
    currency,
    previous_close: null,
    day_change_abs: null,
    day_change_pct: null,
  };
}

function analytics(partial: Partial<AnalyticsResponse>): AnalyticsResponse {
  return {
    total_market_value: "0",
    total_cost_basis: "0",
    total_unrealized_pl: "0",
    total_unrealized_pl_pct: null,
    positions: [],
    allocations: {},
    ...partial,
  };
}

describe("KpiBand", () => {
  it("renders single-currency totals in the display currency, not a hardcoded $", () => {
    render(
      <KpiBand
        loading={false}
        analytics={analytics({
          total_market_value: "6000",
          total_cost_basis: "5000",
          total_unrealized_pl: "1000",
          total_unrealized_pl_pct: "0.2",
          positions: [pos("2330.TW", "TWD", "6000", "1000")],
          currencies_present: ["TWD"],
          display_currency: "TWD",
        })}
      />,
    );
    // TWD renders as NT$ with no fractional part; there must be no bare "$6,000".
    expect(screen.getByText(/NT\$6,000/)).toBeTruthy();
    expect(screen.getByText(/\+NT\$1,000/)).toBeTruthy();
    expect(screen.queryByTestId("kpi-band")?.getAttribute("data-mixed-currency")).toBeNull();
  });

  it("segregates per-currency subtotals when the portfolio is multi-currency", () => {
    render(
      <KpiBand
        loading={false}
        analytics={analytics({
          // Combined totals arrive null/None in mixed mode and must not be shown.
          total_market_value: "None",
          total_unrealized_pl: "None",
          positions: [
            pos("AAPL", "USD", "1500", "500"),
            pos("2330.TW", "TWD", "3000", "500"),
          ],
          currencies_present: ["TWD", "USD"],
          display_currency: "USD",
        })}
      />,
    );
    const band = screen.getByTestId("kpi-band");
    expect(band.getAttribute("data-mixed-currency")).toBe("true");
    expect(screen.getByTestId("kpi-currency-USD").textContent).toMatch(/\$1,500/);
    expect(screen.getByTestId("kpi-currency-TWD").textContent).toMatch(/NT\$3,000/);
    // No combined NAV cell exists in mixed mode.
    expect(screen.queryByText("Total NAV")).toBeNull();
  });
});
