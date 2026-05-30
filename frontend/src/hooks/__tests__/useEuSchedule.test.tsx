import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/earnings-update";
import { useEuSchedule } from "../useEuSchedule";

afterEach(() => vi.restoreAllMocks());

describe("useEuSchedule", () => {
  it("loads schedule and exposes a byTicker map", async () => {
    vi.spyOn(api, "fetchSchedule").mockResolvedValue({
      schedule: [
        { id: "s1", ticker: "MSFT.US", fiscal_date: "2026-06-15", release_timing: "post_market", scheduled_run_at: "2026-06-15T23:00:00Z", status: "pending", report_id: null, eps_estimate: null, revenue_estimate: null, attempts: 0 },
      ],
    });
    const { result } = renderHook(() => useEuSchedule());
    await waitFor(() => expect(result.current.schedule.length).toBe(1));
    expect(result.current.byTicker.get("MSFT.US")?.fiscal_date).toBe("2026-06-15");
  });

  it("byTicker ignores reported rows — pending wins even if reported has earlier date", async () => {
    vi.spyOn(api, "fetchSchedule").mockResolvedValue({
      schedule: [
        { id: "s1", ticker: "AAPL.US", fiscal_date: "2026-03-01", release_timing: "post_market", scheduled_run_at: "2026-03-01T23:00:00Z", status: "reported", report_id: "r1", eps_estimate: null, revenue_estimate: null, attempts: 1 },
        { id: "s2", ticker: "AAPL.US", fiscal_date: "2026-06-15", release_timing: "post_market", scheduled_run_at: "2026-06-15T23:00:00Z", status: "pending", report_id: null, eps_estimate: null, revenue_estimate: null, attempts: 0 },
      ],
    });
    const { result } = renderHook(() => useEuSchedule());
    await waitFor(() => expect(result.current.schedule.length).toBe(2));
    // The reported row (earlier date) must NOT win; byTicker must return the pending one.
    expect(result.current.byTicker.get("AAPL.US")?.id).toBe("s2");
    expect(result.current.byTicker.get("AAPL.US")?.status).toBe("pending");
  });
});
