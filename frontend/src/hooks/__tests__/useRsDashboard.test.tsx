import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/retail-sentiment";
import { useRsDashboard } from "../useRsDashboard";

describe("useRsDashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls getDashboard once on mount", async () => {
    const spy = vi.spyOn(api, "getDashboard").mockResolvedValue({
      tickers: [],
      snapshots: [],
      generated_at: new Date().toISOString(),
    });
    const { result } = renderHook(() => useRsDashboard(null));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("surfaces fetch errors", async () => {
    vi.spyOn(api, "getDashboard").mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useRsDashboard(null));
    await waitFor(() => {
      expect(result.current.error?.message).toBe("boom");
    });
  });
});
