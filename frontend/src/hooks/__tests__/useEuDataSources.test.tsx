import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useEuDataSources } from "../useEuDataSources";
import * as api from "../../api/earnings-update";
import type { DataSource } from "../../api/earnings-update";

const EODHD: DataSource = {
  key: "eodhd",
  display_name: "EODHD",
  category: "financial",
  routing: "curated",
  available: true,
  enabled: true,
  unavailable_reason: null,
};
const WS_OFF: DataSource = {
  key: "model_web_search",
  display_name: "Web search",
  category: "web_search",
  routing: "model_native",
  available: false,
  enabled: false,
  unavailable_reason: "model_no_web_search",
};

describe("useEuDataSources", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches on mount and refetches when the model changes", async () => {
    const spy = vi
      .spyOn(api, "getEuDataSources")
      .mockResolvedValue({ sources: [EODHD, WS_OFF] });

    const { result, rerender } = renderHook(
      ({ pk, m }) => useEuDataSources(pk, m),
      { initialProps: { pk: "anthropic", m: "claude-sonnet-4-6" } },
    );

    await waitFor(() => expect(result.current.sources).not.toBeNull());
    expect(result.current.sources).toHaveLength(2);
    expect(spy).toHaveBeenCalledWith({ provider_kind: "anthropic", model: "claude-sonnet-4-6" });

    rerender({ pk: "anthropic", m: "claude-haiku-4-5-20251001" });
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ provider_kind: "anthropic", model: "claude-haiku-4-5-20251001" }),
    );
  });
});
