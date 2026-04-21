import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { fetchJson, ApiError } from "./client";

describe("fetchJson", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("parses JSON on 200", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ) as unknown as typeof fetch;

    const body = await fetchJson<{ ok: boolean }>("/x");
    expect(body).toEqual({ ok: true });
  });

  it("sends credentials: include by default", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response("null", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = spy as unknown as typeof fetch;

    await fetchJson("/x");
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("include");
  });

  it("throws ApiError with status on 4xx", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "nope" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    await expect(fetchJson("/x")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });
  });

  it("returns null for 204 No Content", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;

    const body = await fetchJson("/x");
    expect(body).toBeNull();
  });

  it("wraps network failures as ApiError with status 0", async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Network request failed")) as unknown as typeof fetch;

    await expect(fetchJson("/x")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });
});

export class _Touch extends ApiError {}
