import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createSchedule,
  deleteSchedule,
  fetchConfig,
  fetchReports,
  fetchSchedules,
  updateConfig,
  updateSchedule,
} from "../morning-briefing";

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

describe("morning-briefing api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchConfig GETs /config", async () => {
    const body = {
      report_length: "normal",
      enabled_section_ids: [],
      section_topics: {},
      custom_sections: [],
      reference_portfolio: false,
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson(body));
    vi.stubGlobal("fetch", fetchMock);
    const result = await fetchConfig();
    expect(result).toEqual(body);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/departments/morning-briefing/config",
    );
  });

  it("updateConfig PUTs /config with body", async () => {
    const body = {
      report_length: "concise",
      enabled_section_ids: ["executive_summary"],
      section_topics: {},
      custom_sections: [],
      reference_portfolio: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(okJson(body));
    vi.stubGlobal("fetch", fetchMock);
    await updateConfig(body as never);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string).reference_portfolio).toBe(true);
  });

  it("fetchSchedules GETs /schedules and returns the list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchMock);
    const r = await fetchSchedules();
    expect(r).toEqual([]);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/departments/morning-briefing/schedules",
    );
  });

  it("createSchedule POSTs /schedules", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      okJson({
        id: "s_1",
        time: "07:00",
        timezone: "America/New_York",
        days_of_week: ["mon"],
        label: "Pre-Market",
        is_enabled: true,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const r = await createSchedule({
      time: "07:00",
      timezone: "America/New_York",
      days_of_week: ["mon"],
      label: "Pre-Market",
    });
    expect(r.id).toBe("s_1");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });

  it("updateSchedule PATCHes /schedules/:id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      okJson({
        id: "s_1",
        time: "08:00",
        timezone: "America/New_York",
        days_of_week: ["mon"],
        label: "Updated",
        is_enabled: true,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const r = await updateSchedule("s_1", {
      time: "08:00",
      timezone: "America/New_York",
      days_of_week: ["mon"],
      label: "Updated",
    });
    expect(r.label).toBe("Updated");
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/departments/morning-briefing/schedules/s_1",
    );
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH");
  });

  it("deleteSchedule DELETEs /schedules/:id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok204());
    vi.stubGlobal("fetch", fetchMock);
    await deleteSchedule("s_1");
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/departments/morning-briefing/schedules/s_1",
    );
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });

  it("fetchReports hits shared /reports with department filter", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const r = await fetchReports();
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/reports?department=morning_briefing",
    );
    expect(r.reports).toEqual([]);
  });
});
