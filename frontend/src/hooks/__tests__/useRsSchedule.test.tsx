import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/retail-sentiment";
import { useRsSchedule } from "../useRsSchedule";

describe("useRsSchedule", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("hydrates schedule from getSchedule on mount", async () => {
    vi.spyOn(api, "getSchedule").mockResolvedValue({
      schedule: {
        id: "s1",
        time: "08:00",
        timezone: "UTC",
        days_of_week: ["mon"],
        label: "x",
        is_enabled: true,
      },
    });
    const { result } = renderHook(() => useRsSchedule());
    await waitFor(() => {
      expect(result.current.schedule?.id).toBe("s1");
    });
  });

  it("save calls putSchedule and updates schedule", async () => {
    vi.spyOn(api, "getSchedule").mockResolvedValue({ schedule: null });
    const put = vi.spyOn(api, "putSchedule").mockResolvedValue({
      id: "s2",
      time: "09:00",
      timezone: "UTC",
      days_of_week: ["tue"],
      label: "y",
      is_enabled: true,
    });
    const { result } = renderHook(() => useRsSchedule());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.save({
        time: "09:00",
        timezone: "UTC",
        days_of_week: ["tue"],
        label: "y",
      });
    });
    expect(put).toHaveBeenCalled();
    expect(result.current.schedule?.id).toBe("s2");
  });

  it("surfaces error when getSchedule rejects", async () => {
    vi.spyOn(api, "getSchedule").mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useRsSchedule());
    await waitFor(() => {
      expect(result.current.error?.message).toBe("boom");
    });
  });
});
