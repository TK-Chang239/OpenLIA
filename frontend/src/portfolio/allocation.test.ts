import { describe, expect, it } from "vitest";

import type { AnalyticsResponse, PortfolioHolding, PositionAnalytic } from "../api/portfolio";
import { computeAllocation, UNTAGGED } from "./allocation";

function holding(id: string, groups: string[], currency = "USD"): PortfolioHolding {
  return {
    id,
    ticker: id,
    name: null,
    shares: "1",
    cost_basis: "1",
    currency,
    groups,
    notes_text: null,
    added_at: "",
    updated_at: "",
  };
}

function pos(holdingId: string, marketValue: string, currency = "USD"): PositionAnalytic {
  return {
    holding_id: holdingId,
    ticker: holdingId,
    shares: "1",
    cost_basis: "1",
    last_price: marketValue,
    market_value: marketValue,
    unrealized_pl: "0",
    unrealized_pl_pct: "0",
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

describe("computeAllocation", () => {
  it("computes group weights for a single-currency portfolio", () => {
    const holdings = [holding("A", ["Tech"]), holding("B", [])];
    const a = analytics({
      total_market_value: "100",
      positions: [pos("A", "75"), pos("B", "25")],
      currencies_present: ["USD"],
      display_currency: "USD",
    });
    const rows = computeAllocation(holdings, a);
    expect(rows.map((r) => r.group)).toEqual(["Tech", UNTAGGED]);
    expect(rows[0].pct).toBeCloseTo(75);
    expect(rows[1].pct).toBeCloseTo(25);
  });

  it("returns no rows when the portfolio spans more than one currency", () => {
    const holdings = [holding("A", ["Tech"], "USD"), holding("B", ["Tech"], "TWD")];
    const a = analytics({
      // Combined total is null on the wire in mixed mode; must not be relied upon.
      total_market_value: "None",
      positions: [pos("A", "1500", "USD"), pos("B", "3000", "TWD")],
      currencies_present: ["TWD", "USD"],
      display_currency: "USD",
    });
    expect(computeAllocation(holdings, a)).toEqual([]);
  });
});
