import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/retail-sentiment";
import { useRsConfig } from "../useRsConfig";

const baseConfig = {
  id: "c1",
  user_id: "u1",
  active_tab: "overview",
  metric_settings: {},
  filter_presets: [],
  refresh_interval_minutes: 60,
};

describe("useRsConfig", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("hydrates from getConfig on mount", async () => {
    vi.spyOn(api, "getConfig").mockResolvedValue(baseConfig);
    const { result } = renderHook(() => useRsConfig());
    await waitFor(() => expect(result.current.config?.id).toBe("c1"));
  });

  it("optimistically updates config and persists via updateConfig", async () => {
    vi.spyOn(api, "getConfig").mockResolvedValue(baseConfig);
    const upd = vi.spyOn(api, "updateConfig").mockResolvedValue({
      ...baseConfig,
      active_tab: "evidence",
    });
    const { result } = renderHook(() => useRsConfig());
    await waitFor(() => expect(result.current.config).not.toBeNull());

    await act(async () => {
      await result.current.save({ active_tab: "evidence" });
    });

    expect(upd).toHaveBeenCalledWith({ active_tab: "evidence" });
    expect(result.current.config?.active_tab).toBe("evidence");
  });

  it("rolls back on save failure", async () => {
    vi.spyOn(api, "getConfig").mockResolvedValue(baseConfig);
    vi.spyOn(api, "updateConfig").mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => useRsConfig());
    await waitFor(() => expect(result.current.config).not.toBeNull());

    await act(async () => {
      try {
        await result.current.save({ active_tab: "insights" });
      } catch {
        // expected
      }
    });

    // Optimistic state was rolled back to original.
    expect(result.current.config?.active_tab).toBe("overview");
    expect(result.current.error?.message).toBe("boom");
  });
});
