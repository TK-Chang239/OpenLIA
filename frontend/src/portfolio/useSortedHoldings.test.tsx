import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";

import type { PortfolioHolding, PositionAnalytic } from "../api/portfolio";
import { useSortedHoldings } from "./useSortedHoldings";

const mk = (id: string, ticker: string): PortfolioHolding => ({
  id,
  ticker,
  name: null,
  shares: null,
  cost_basis: null,
  currency: "USD",
  groups: [],
  notes_text: null,
  added_at: "",
  updated_at: "",
});

describe("useSortedHoldings", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("defaults to A→Z order", () => {
    const holdings = [mk("1", "MSFT"), mk("2", "AAPL"), mk("3", "NVDA")];
    const prices = new Map();
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, prices, "all"),
    );
    expect(result.current.sorted.map((h) => h.ticker)).toEqual([
      "AAPL",
      "MSFT",
      "NVDA",
    ]);
    expect(result.current.sortKey).toBe("alpha-asc");
  });

  it("switches to Z→A and persists per group", () => {
    const holdings = [mk("1", "AAPL"), mk("2", "MSFT")];
    const prices = new Map();
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, prices, "Tech"),
    );
    act(() => result.current.setSortKey("alpha-desc"));
    expect(result.current.sorted.map((h) => h.ticker)).toEqual([
      "MSFT",
      "AAPL",
    ]);
    expect(window.localStorage.getItem("portfolio:sort:Tech")).toBe(
      "alpha-desc",
    );
  });

  it("sorts by price descending using the analytics map", () => {
    const holdings = [mk("a", "A"), mk("b", "B")];
    const prices = new Map<string, PositionAnalytic | undefined>([
      ["a", { ticker: "A", last_price: "10" } as PositionAnalytic],
      ["b", { ticker: "B", last_price: "100" } as PositionAnalytic],
    ]);
    const { result } = renderHook(() => useSortedHoldings(holdings, prices, "x"));
    act(() => result.current.setSortKey("price-desc"));
    expect(result.current.sorted.map((h) => h.ticker)).toEqual(["B", "A"]);
  });
});
