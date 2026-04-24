import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/earnings-update";
import { useEuConfig } from "../useEuConfig";

beforeEach(() => {
  vi.restoreAllMocks();
});

const defaults: api.EuConfig = {
  report_length: "normal",
  enabled_section_ids: ["quick_take"],
  custom_sections: [],
};

describe("useEuConfig", () => {
  it("loads config on mount", async () => {
    vi.spyOn(api, "fetchConfig").mockResolvedValue(defaults);
    const { result } = renderHook(() => useEuConfig());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.config?.report_length).toBe("normal");
  });

  it("save() PUTs new config and updates local state", async () => {
    vi.spyOn(api, "fetchConfig").mockResolvedValue(defaults);
    const next: api.EuConfig = { ...defaults, report_length: "concise" };
    vi.spyOn(api, "updateConfig").mockResolvedValue(next);
    const { result } = renderHook(() => useEuConfig());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.save(next);
    });
    expect(result.current.config?.report_length).toBe("concise");
  });
});
