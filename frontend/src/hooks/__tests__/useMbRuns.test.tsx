import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/morning-briefing";
import { useMbRuns } from "../useMbRuns";
import type { MbRunSummary } from "../../api/morning-briefing";

const RUN: MbRunSummary = {
  report_id: "r_1",
  subject: "Morning Briefing — Monday 2 June 2026",
  trigger_kind: "on_demand",
  schedule_id: null,
  template_id: "mb_default",
  instructions_id: null,
  language: "en",
  length: "normal",
  status: "completed",
  created_at: "2026-06-02T07:00:00Z",
  completed_at: "2026-06-02T07:05:00Z",
  reasoning_effort: null,
  highlights: null,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useMbRuns", () => {
  it("loads runs on mount and exposes refresh", async () => {
    vi.spyOn(api, "listMbRuns").mockResolvedValue([RUN]);

    const { result } = renderHook(() => useMbRuns());

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.runs).toHaveLength(1);
    expect(result.current.runs[0].report_id).toBe("r_1");
    expect(result.current.error).toBeNull();
  });

  it("passes status filter to listMbRuns", async () => {
    const spy = vi.spyOn(api, "listMbRuns").mockResolvedValue([]);

    const { result } = renderHook(() => useMbRuns("completed"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(spy).toHaveBeenCalledWith("completed");
  });

  it("exposes error on fetch failure", async () => {
    vi.spyOn(api, "listMbRuns").mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useMbRuns());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error?.message).toBe("network error");
    expect(result.current.runs).toHaveLength(0);
  });

  it("refresh re-fetches and updates runs", async () => {
    const spy = vi
      .spyOn(api, "listMbRuns")
      .mockResolvedValueOnce([RUN])
      .mockResolvedValueOnce([]);

    const { result } = renderHook(() => useMbRuns());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.runs).toHaveLength(1);

    void result.current.refresh();
    await waitFor(() => expect(result.current.runs).toHaveLength(0));
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
