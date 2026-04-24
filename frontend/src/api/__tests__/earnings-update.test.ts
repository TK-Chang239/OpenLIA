import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  addWatchlistEntry,
  createSchedule,
  deleteSchedule,
  fetchConfig,
  fetchRecentReports,
  fetchSchedules,
  fetchWatchlist,
  removeWatchlistEntry,
  reportStreamUrl,
  updateConfig,
  updateSchedule,
  type EuConfig,
} from "../earnings-update";

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

describe("earnings-update api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchWatchlist GETs /watchlist", async () => {
    const body = { entries: [] };
    const fetchMock = vi.fn().mockResolvedValue(okJson(body));
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchWatchlist();
    expect(result).toEqual(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/watchlist");
    expect(init.credentials).toBe("include");
  });

  it("addWatchlistEntry POSTs ticker", async () => {
    const body = {
      id: "x",
      ticker: "AAPL",
      company_name: "Apple Inc.",
      next_earnings_date: "2026-04-25",
      release_timing: "post_market",
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson(body, 201));
    vi.stubGlobal("fetch", fetchMock);
    const result = await addWatchlistEntry("AAPL");
    expect(result.ticker).toBe("AAPL");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/watchlist");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ ticker: "AAPL" });
  });

  it("removeWatchlistEntry DELETEs the entry id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok204());
    vi.stubGlobal("fetch", fetchMock);
    await removeWatchlistEntry("xyz");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/watchlist/xyz");
    expect(init.method).toBe("DELETE");
  });

  it("fetchConfig GETs /config", async () => {
    const body: EuConfig = {
      report_length: "normal",
      enabled_section_ids: ["quick_take"],
      custom_sections: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson(body));
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchConfig();
    expect(result).toEqual(body);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/config");
  });

  it("updateConfig PUTs the full body", async () => {
    const body: EuConfig = {
      report_length: "concise",
      enabled_section_ids: [],
      custom_sections: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson(body));
    vi.stubGlobal("fetch", fetchMock);
    await updateConfig({
      report_length: "concise",
      enabled_section_ids: ["quick_take"],
      custom_sections: [],
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/config");
    expect(init.method).toBe("PUT");
    const sent = JSON.parse(init.body as string);
    expect(sent.enabled_section_ids).toEqual(["quick_take"]);
  });

  it("fetchSchedules GETs /schedules and wraps the list", async () => {
    const row = {
      id: "s1",
      user_id: "u1",
      time: "06:00",
      timezone: "America/New_York",
      days_of_week: [0, 1],
      label: "a",
      is_enabled: true,
      created_at: "2026-04-20T00:00:00Z",
      last_run_at: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson([row]));
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchSchedules();
    expect(result.schedules).toHaveLength(1);
    expect(result.schedules[0].id).toBe("s1");
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/schedules");
  });

  it("createSchedule POSTs", async () => {
    const row = {
      id: "s1",
      user_id: "u1",
      time: "06:00",
      timezone: "America/New_York",
      days_of_week: [1],
      label: "a",
      is_enabled: true,
      created_at: "2026-04-20T00:00:00Z",
      last_run_at: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson(row, 201));
    vi.stubGlobal("fetch", fetchMock);
    const result = await createSchedule({
      time: "06:00",
      timezone: "America/New_York",
      days_of_week: [1],
      label: "a",
      is_enabled: true,
    });
    expect(result.id).toBe("s1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/schedules");
    expect(init.method).toBe("POST");
  });

  it("updateSchedule PATCHes the schedule id", async () => {
    const row = {
      id: "s1",
      user_id: "u1",
      time: "07:00",
      timezone: "America/New_York",
      days_of_week: [1],
      label: "b",
      is_enabled: true,
      created_at: "2026-04-20T00:00:00Z",
      last_run_at: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson(row));
    vi.stubGlobal("fetch", fetchMock);
    await updateSchedule("s1", {
      time: "07:00",
      timezone: "America/New_York",
      days_of_week: [1],
      label: "b",
      is_enabled: true,
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/schedules/s1");
    expect(init.method).toBe("PATCH");
  });

  it("deleteSchedule DELETEs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ deleted: "s1" }));
    vi.stubGlobal("fetch", fetchMock);
    await deleteSchedule("s1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/schedules/s1");
    expect(init.method).toBe("DELETE");
  });

  it("fetchRecentReports GETs /reports with limit", async () => {
    const body = { reports: [] };
    const fetchMock = vi.fn().mockResolvedValue(okJson(body));
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchRecentReports(7);
    expect(result).toEqual(body);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/earnings-update/reports?limit=7");
  });

  it("reportStreamUrl returns the POST endpoint path", () => {
    expect(reportStreamUrl()).toBe("/api/departments/earnings-update/report");
  });
});
