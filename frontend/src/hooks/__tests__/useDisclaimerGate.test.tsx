import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useDisclaimerGate } from "../useDisclaimerGate";

beforeEach(() => {
  localStorage.clear();
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url === "/api/disclaimer")
      return Promise.resolve({
        ok: true,
        json: async () => ({ text: "...", version: "1.0.0" }),
      });
    if (url === "/api/disclaimer/status")
      return Promise.resolve({
        ok: true,
        json: async () => ({
          current_version: "1.0.0",
          accepted: false,
          accepted_version: null,
        }),
      });
    return Promise.reject(new Error("unexpected url"));
  }) as unknown as typeof fetch;
});

describe("useDisclaimerGate (company mode)", () => {
  it("flags needsAcceptance when server reports accepted=false", async () => {
    const { result } = renderHook(() => useDisclaimerGate("company"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.needsAcceptance).toBe(true);
    expect(result.current.disclaimer?.version).toBe("1.0.0");
  });
});
