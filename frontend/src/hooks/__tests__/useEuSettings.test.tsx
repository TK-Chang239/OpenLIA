import { renderHook, waitFor, act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/earnings-update";
import { useEuSettings } from "../useEuSettings";

const base: api.EuSettings = {
  provider_kind: "anthropic", model: "claude-sonnet-4-6", template_id: "eu_default",
  language: "en", length: "normal", reasoning_effort: null,
  financial_enabled: true, calendar_enabled: true, web_search_enabled: false,
  instructions_id: null,
};

afterEach(() => { vi.restoreAllMocks(); });

describe("useEuSettings", () => {
  it("loads settings then saves", async () => {
    vi.spyOn(api, "fetchSettings").mockResolvedValue(base);
    const saveSpy = vi.spyOn(api, "updateSettings").mockResolvedValue({ ...base, web_search_enabled: true });
    const { result } = renderHook(() => useEuSettings());
    await waitFor(() => expect(result.current.settings).not.toBeNull());
    await act(async () => { await result.current.save({ ...base, web_search_enabled: true }); });
    expect(saveSpy).toHaveBeenCalled();
    expect(result.current.settings?.web_search_enabled).toBe(true);
  });
});
