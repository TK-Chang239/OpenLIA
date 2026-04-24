import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/earnings-update";
import { useEuWatchlist } from "../useEuWatchlist";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("useEuWatchlist", () => {
  it("loads entries on mount", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({
      entries: [
        {
          id: "1",
          ticker: "AAPL",
          company_name: "Apple Inc.",
          next_earnings_date: "2026-04-25",
          release_timing: "post_market",
        },
      ],
    });
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].ticker).toBe("AAPL");
  });

  it("add() calls api and prepends entry", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "addWatchlistEntry").mockResolvedValue({
      id: "2",
      ticker: "TSLA",
      company_name: "Tesla",
      next_earnings_date: null,
      release_timing: null,
    });
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.add("TSLA");
    });
    expect(result.current.entries.map((e) => e.ticker)).toContain("TSLA");
  });

  it("remove() optimistically removes then restores on failure", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({
      entries: [
        {
          id: "1",
          ticker: "AAPL",
          company_name: "Apple",
          next_earnings_date: null,
          release_timing: null,
        },
      ],
    });
    vi.spyOn(api, "removeWatchlistEntry").mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.entries).toHaveLength(1));
    await expect(
      act(async () => {
        await result.current.remove("1");
      }),
    ).rejects.toThrow();
    expect(result.current.entries).toHaveLength(1);
  });
});
