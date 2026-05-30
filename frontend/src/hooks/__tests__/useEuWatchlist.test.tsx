import { renderHook, waitFor, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/earnings-update";
import { useEuWatchlist } from "../useEuWatchlist";

afterEach(() => { vi.restoreAllMocks(); });

describe("useEuWatchlist (v2)", () => {
  it("loads, adds, and removes entries", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "addWatchlistEntry").mockResolvedValue({ id: "1", ticker: "MSFT.US", company_name: null, created_at: "" });
    vi.spyOn(api, "removeWatchlistEntry").mockResolvedValue(undefined);
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.add("MSFT.US"); });
    expect(result.current.entries.some((e) => e.ticker === "MSFT.US")).toBe(true);
    await act(async () => { await result.current.remove("1"); });
    expect(result.current.entries.length).toBe(0);
  });
});
