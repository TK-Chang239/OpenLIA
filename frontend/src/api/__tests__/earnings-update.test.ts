import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "../client";
import {
  fetchWatchlist,
  addWatchlistEntry,
  syncWatchlist,
  fetchSettings,
  updateSettings,
  fetchTemplates,
  fetchSchedule,
  startRun,
  fetchRuns,
  getRun,
  deleteRun,
  cancelRun,
  runEventsUrl,
  EU_TERMINAL_EVENT_TYPES,
} from "../earnings-update";

afterEach(() => { vi.restoreAllMocks(); });

function mockJson(value: unknown) {
  return vi.spyOn(client, "fetchJson").mockResolvedValue(value as never);
}

describe("earnings-update v2 client", () => {
  it("fetchWatchlist hits v2 watchlist", async () => {
    const spy = mockJson({ entries: [] });
    await fetchWatchlist();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/watchlist",
    );
  });

  it("addWatchlistEntry POSTs ticker", async () => {
    const spy = mockJson({
      id: "1",
      ticker: "MSFT.US",
      company_name: null,
      created_at: "",
    });
    await addWatchlistEntry("MSFT.US");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/watchlist",
      { method: "POST", json: { ticker: "MSFT.US" } },
    );
  });

  it("syncWatchlist POSTs to /watchlist/sync", async () => {
    const spy = mockJson({ synced: 2 });
    const r = await syncWatchlist();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/watchlist/sync",
      { method: "POST" },
    );
    expect(r.synced).toBe(2);
  });

  it("updateSettings PUTs settings", async () => {
    const settings = {
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
      template_id: "eu_default",
      language: "en",
      length: "normal" as const,
      reasoning_effort: null,
      enabled_provider_ids: ["eodhd"],
      web_search_enabled: false,
      instructions_id: null,
    };
    const spy = mockJson(settings);
    await updateSettings(settings);
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/settings",
      { method: "PUT", json: settings },
    );
  });

  it("fetchSettings GETs settings", async () => {
    const spy = mockJson({
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
      template_id: "eu_default",
      language: "en",
      length: "normal",
      reasoning_effort: null,
      enabled_provider_ids: ["eodhd"],
      web_search_enabled: false,
      instructions_id: null,
    });
    await fetchSettings();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/settings",
    );
  });

  it("fetchTemplates GETs templates", async () => {
    const spy = mockJson({ templates: [] });
    await fetchTemplates();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/templates",
    );
  });

  it("fetchSchedule GETs schedule", async () => {
    const spy = mockJson({ schedule: [] });
    await fetchSchedule();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/schedule",
    );
  });

  it("startRun returns report_id", async () => {
    mockJson({ report_id: "r1" });
    const r = await startRun({ ticker: "AAPL.US" });
    expect(r.report_id).toBe("r1");
  });

  it("fetchRuns passes status filter", async () => {
    const spy = mockJson([]);
    await fetchRuns("completed");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/runs?status=completed",
    );
  });

  it("fetchRuns without filter omits query string", async () => {
    const spy = mockJson([]);
    await fetchRuns();
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/runs",
    );
  });

  it("getRun fetches run detail by id", async () => {
    const spy = mockJson({
      report: {
        report_id: "r1",
        ticker: "AAPL.US",
        subject: "AAPL.US Q3",
        template_id: "eu_default",
        trigger_kind: "on_demand",
        fiscal_date: null,
        language: "en",
        length: "normal",
        status: "completed",
        created_at: "",
        completed_at: null,
        reasoning_effort: null,
      },
      error_message: null,
      sections: [],
      charts: [],
      citations: [],
      cover: null,
    });
    await getRun("r1");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/runs/r1",
    );
  });

  it("deleteRun DELETEs by id", async () => {
    const spy = mockJson(null);
    await deleteRun("r1");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/runs/r1",
      { method: "DELETE" },
    );
  });

  it("runEventsUrl builds the SSE path", () => {
    expect(runEventsUrl("r1")).toBe(
      "/api/departments/earnings-update/v2/runs/r1/events",
    );
  });

  it("cancelRun POSTs cancel", async () => {
    const spy = mockJson({ cancelled: true });
    await cancelRun("r1");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/earnings-update/v2/runs/r1/cancel",
      { method: "POST" },
    );
  });

  it("terminal event set covers run.completed/failed/cancelled/snapshot", () => {
    expect(EU_TERMINAL_EVENT_TYPES.has("run.completed")).toBe(true);
    expect(EU_TERMINAL_EVENT_TYPES.has("run.failed")).toBe(true);
    expect(EU_TERMINAL_EVENT_TYPES.has("run.cancelled")).toBe(true);
    expect(EU_TERMINAL_EVENT_TYPES.has("run.snapshot")).toBe(true);
    expect(EU_TERMINAL_EVENT_TYPES.has("section.written")).toBe(false);
  });
});
