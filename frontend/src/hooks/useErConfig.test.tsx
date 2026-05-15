import { renderHook, act, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ER_CONFIG_DEFAULTS } from "../api/equity-research";
import { useErConfig } from "./useErConfig";

function okJson(body: unknown) {
  return {
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    json: async () => body,
  } as unknown as Response;
}

const CACHE_KEY = "openlia.er_config.v1";

const serverBody = {
  report_mode: "stock_update" as const,
  report_length: "elaborative" as const,
  sections_by_mode: {
    stock_initiation: ["Overview"],
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

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("useErConfig", () => {
  it("returns ER_CONFIG_DEFAULTS synchronously on first render so the page can paint without waiting", () => {
    // Fetch never resolves — simulates a pending /config GET.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));

    const { result } = renderHook(() => useErConfig());

    expect(result.current.config).toEqual(ER_CONFIG_DEFAULTS);
    expect(result.current.loading).toBe(true);
  });

  it("seeds initial config from localStorage cache when present (instant paint with last-known values)", () => {
    window.localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ ...ER_CONFIG_DEFAULTS, report_mode: "sector_research" }),
    );
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));

    const { result } = renderHook(() => useErConfig());

    expect(result.current.config.report_mode).toBe("sector_research");
  });

  it("upgrades to the real config and writes it to the cache once the fetch resolves", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okJson(serverBody)));

    const { result } = renderHook(() => useErConfig());
    expect(result.current.config.report_mode).toBe("stock_initiation");

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.config.report_mode).toBe("stock_update");
    expect(result.current.config.report_length).toBe("elaborative");

    const cached = JSON.parse(
      window.localStorage.getItem(CACHE_KEY) ?? "null",
    );
    expect(cached?.report_mode).toBe("stock_update");
  });

  it("keeps a usable config (cache or defaults) and surfaces an error when the fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network down")),
    );

    const { result } = renderHook(() => useErConfig());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error?.message).toBe("network down");
    expect(result.current.config).toEqual(ER_CONFIG_DEFAULTS);
  });

  it("patch() calls PUT, updates local state, and refreshes the cache", async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce(okJson(serverBody));
    fetchMock.mockResolvedValueOnce(
      okJson({ ...serverBody, report_mode: "sector_research" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useErConfig());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.patch({ report_mode: "sector_research" });
    });
    expect(result.current.config.report_mode).toBe("sector_research");
    const cached = JSON.parse(
      window.localStorage.getItem(CACHE_KEY) ?? "null",
    );
    expect(cached?.report_mode).toBe("sector_research");
  });
});
