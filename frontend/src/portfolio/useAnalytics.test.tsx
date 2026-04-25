import { renderHook, waitFor, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/portfolio";
import { useAnalytics } from "./useAnalytics";

const empty: api.AnalyticsResponse = {
  total_market_value: "0",
  total_cost_basis: "0",
  total_unrealized_pl: "0",
  total_unrealized_pl_pct: null,
  positions: [],
  allocations: {},
};

describe("useAnalytics", () => {
  beforeEach(() => {
    vi.spyOn(api, "fetchAnalytics").mockResolvedValue(empty);
    vi.spyOn(api, "refreshPrices").mockResolvedValue({ prices: {} });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads analytics on mount", async () => {
    const { result } = renderHook(() => useAnalytics());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.analytics?.total_market_value).toBe("0");
  });

  it("refresh chains refreshPrices then reload", async () => {
    const { result } = renderHook(() => useAnalytics());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.refresh();
    });
    expect(api.refreshPrices).toHaveBeenCalled();
    expect(api.fetchAnalytics).toHaveBeenCalledTimes(2);
  });
});
