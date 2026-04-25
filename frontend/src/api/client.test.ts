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

describe("fetchJson VITE_API_BASE_URL", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  it("prefixes relative paths with VITE_API_BASE_URL when set", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    const spy = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await fetchJson("/api/x");
    expect(spy.mock.calls[0][0]).toBe("https://api.example.com/api/x");
  });

  it("leaves absolute http(s) URLs untouched", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    const spy = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await fetchJson("https://other.example.com/foo");
    expect(spy.mock.calls[0][0]).toBe("https://other.example.com/foo");
  });

  it("falls back to the bare relative path when env is empty", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const spy = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await fetchJson("/api/y");
    expect(spy.mock.calls[0][0]).toBe("/api/y");
  });

  it("strips trailing slashes from the base", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com///");
    const spy = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await fetchJson("/api/z");
    expect(spy.mock.calls[0][0]).toBe("https://api.example.com/api/z");
  });
});

export class _Touch extends ApiError {}
