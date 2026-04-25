import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/portfolio";
import { useHoldings } from "./useHoldings";

const sample: api.PortfolioHolding = {
  id: "1",
  ticker: "AAPL",
  name: null,
  shares: null,
  cost_basis: null,
  currency: "USD",
  groups: [],
  notes_text: null,
  added_at: "",
  updated_at: "",
};

describe("useHoldings", () => {
  beforeEach(() => {
    vi.spyOn(api, "fetchHoldings").mockResolvedValue([sample]);
    vi.spyOn(api, "createHolding").mockResolvedValue({
      ...sample,
      id: "2",
      ticker: "MSFT",
    });
    vi.spyOn(api, "deleteHolding").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads holdings on mount", async () => {
    const { result } = renderHook(() => useHoldings());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.holdings).toHaveLength(1);
  });

  it("appends on add", async () => {
    const { result } = renderHook(() => useHoldings());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.add({ ticker: "MSFT" });
    });
    expect(result.current.holdings).toHaveLength(2);
  });

  it("returns snapshot on remove for Undo", async () => {
    const { result } = renderHook(() => useHoldings());
    await waitFor(() => expect(result.current.loading).toBe(false));
    let snapshot: api.PortfolioHolding | undefined;
    await act(async () => {
      snapshot = await result.current.remove("1");
    });
    expect(snapshot?.ticker).toBe("AAPL");
    expect(result.current.holdings).toHaveLength(0);
  });
});
