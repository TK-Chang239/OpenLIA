import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  chatStreamUrl,
  fetchErConfig,
  reportStreamUrl,
  updateErConfig,
  type ErConfig,
} from "../equity-research";

describe("equity-research api", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchErConfig GETs /config and returns typed body", async () => {
    const body: ErConfig = {
      report_mode: "stock_initiation",
      report_length: "normal",
      sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
      custom_sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
      selected_template_id_by_mode: {
        stock_initiation: "default",
        stock_update: "default",
        sector_research: "default",
      },
      web_search_budgets_by_mode: {},
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => body,
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchErConfig();
    expect(result).toEqual(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/config");
    expect(init.credentials).toBe("include");
  });

  it("updateErConfig PUTs a partial patch", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ report_length: "elaborative" }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await updateErConfig({ report_length: "elaborative" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/config");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ report_length: "elaborative" });
  });

  it("reportStreamUrl returns the POST endpoint path", () => {
    expect(reportStreamUrl()).toBe("/api/departments/equity-research/report");
  });

  it("chatStreamUrl returns the POST endpoint path", () => {
    expect(chatStreamUrl()).toBe("/api/departments/equity-research/chat");
  });
});
