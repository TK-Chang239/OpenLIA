import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useErConfig } from "./useErConfig";

function okJson(body: unknown) {
  return {
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    json: async () => body,
  } as unknown as Response;
}

const defaultsBody = {
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
};

describe("useErConfig", () => {
  it("loads config on mount then exposes data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okJson(defaultsBody)));

    const { result } = renderHook(() => useErConfig());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.config?.report_mode).toBe("stock_initiation");
  });

  it("patch() calls PUT then updates local state", async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce(okJson(defaultsBody));
    fetchMock.mockResolvedValueOnce(
      okJson({ ...defaultsBody, report_mode: "stock_update" })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useErConfig());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.patch({ report_mode: "stock_update" });
    });
    expect(result.current.config?.report_mode).toBe("stock_update");
  });
});
