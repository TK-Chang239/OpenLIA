import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "../api/client";
import { setTakeoverPromptHandler, withTakeoverRetry } from "./takeover";

describe("withTakeoverRetry", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("retries the original call after the user accepts takeover", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    setTakeoverPromptHandler(async () => true);

    let calls = 0;
    const op = async (): Promise<{ ok: boolean }> => {
      calls += 1;
      if (calls === 1) {
        throw new ApiError(409, "conflict", { detail: { code: "wizard_session_active" } });
      }
      return { ok: true };
    };

    const result = await withTakeoverRetry(op);
    expect(result).toEqual({ ok: true });
    expect(calls).toBe(2);
    // takeover() POST happened between calls.
    expect(fetchSpy).toHaveBeenCalled();
  });

  it("rethrows when the user declines takeover", async () => {
    setTakeoverPromptHandler(async () => false);
    const op = async (): Promise<unknown> => {
      throw new ApiError(409, "conflict", { detail: { code: "wizard_session_active" } });
    };
    await expect(withTakeoverRetry(op)).rejects.toBeInstanceOf(ApiError);
  });

  it("rethrows non-409 errors unchanged", async () => {
    setTakeoverPromptHandler(async () => true);
    const op = async (): Promise<unknown> => {
      throw new ApiError(500, "boom", null);
    };
    await expect(withTakeoverRetry(op)).rejects.toBeInstanceOf(ApiError);
  });
});
