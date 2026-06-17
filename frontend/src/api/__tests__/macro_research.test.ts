import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  deleteSchedule,
  getDashboard,
  getSchedule,
  listDashboards,
  putSchedule,
  runAssessment,
} from "../macro_research";

function okJson(body: unknown, status = 200) {
  return {
    ok: true,
    status,
    headers: { get: () => "application/json" },
    json: async () => body,
  } as unknown as Response;
}

function ok204() {
  return {
    ok: true,
    status: 204,
    headers: { get: () => "" },
    json: async () => null,
  } as unknown as Response;
}

function errJson(body: unknown, status: number) {
  return {
    ok: false,
    status,
    headers: { get: () => "application/json" },
    json: async () => body,
  } as unknown as Response;
}

describe("macro_research api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("listDashboards GETs /dashboards", async () => {
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(okJson({ dashboards: [] }));
    await listDashboards();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/dashboards",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("getDashboard GETs /dashboards/:slug and returns the response shape", async () => {
    const body = {
      payload: { sources: "x" },
      generated_at: "2026-06-01T00:00:00Z",
      is_stale: false,
      provenance: "live",
    };
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(okJson(body));
    const result = await getDashboard("debt_cycle");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/dashboards/debt_cycle",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(result).toEqual(body);
  });

  it("runAssessment POSTs to the refresh endpoint", async () => {
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(okJson({ job_run_id: "j1", status: "queued" }));
    await runAssessment("world_order");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/dashboards/world_order/refresh",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("runAssessment maps a 409 to already_running instead of throwing", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      errJson(
        { detail: "a 'debt_cycle' dashboard run is already in progress" },
        409,
      ),
    );
    const result = await runAssessment("debt_cycle");
    expect(result).toEqual({ job_run_id: null, status: "already_running" });
  });

  it("runAssessment still throws on other non-ok statuses", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(errJson({ detail: "boom" }, 500));
    await expect(runAssessment("debt_cycle")).rejects.toThrow();
  });

  it("getSchedule GETs /schedule", async () => {
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(okJson({ cron_expression: null }));
    await getSchedule();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/schedule",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("putSchedule PUTs cron_expression", async () => {
    const spy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(okJson({ cron_expression: "0 0 * * 0" }));
    await putSchedule("0 0 * * 0");
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(spy.mock.calls[0][0]).toBe("/api/departments/macro_research/schedule");
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify({ cron_expression: "0 0 * * 0" }));
  });

  it("deleteSchedule DELETEs and returns null on 204", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(ok204());
    const result = await deleteSchedule();
    expect(result).toBeNull();
  });

  it("throws with status on non-ok", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      headers: { get: () => "" },
      json: async () => ({}),
    } as unknown as Response);
    await expect(listDashboards()).rejects.toThrow(/500/);
  });
});
