import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useEuDataSources } from "../useEuDataSources";
import * as api from "../../api/earnings-update";

const SLOT = { available: true, provider_label: "EODHD", unavailable_reason: null };

describe("useEuDataSources", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches on mount and refetches when the model changes", async () => {
    const spy = vi
      .spyOn(api, "getEuDataSources")
      .mockResolvedValue({
        financial: SLOT,
        earnings_calendar: SLOT,
        web_search: { available: false, provider_label: null, unavailable_reason: "model_no_web_search" },
        other_connectors: [],
      });

    const { result, rerender } = renderHook(
      ({ pk, m }) => useEuDataSources(pk, m),
      { initialProps: { pk: "anthropic", m: "claude-sonnet-4-6" } },
    );

    await waitFor(() => expect(result.current.dataSources).not.toBeNull());
    expect(spy).toHaveBeenCalledWith({ provider_kind: "anthropic", model: "claude-sonnet-4-6" });

    rerender({ pk: "anthropic", m: "claude-haiku-4-5-20251001" });
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ provider_kind: "anthropic", model: "claude-haiku-4-5-20251001" }),
    );
  });
});
