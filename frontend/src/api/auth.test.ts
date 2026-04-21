import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getSession, login, logout } from "./auth";
import { ApiError } from "./client";

describe("auth api", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("getSession returns the user on 200", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user: { id: "u1", email: "a@x.com", role: "admin" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const user = await getSession();
    expect(user).toEqual({ id: "u1", email: "a@x.com", role: "admin" });
  });

  it("getSession re-throws ApiError on 401/404 so callers can branch", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;

    await expect(getSession()).rejects.toBeInstanceOf(ApiError);
  });

  it("login posts credentials and returns the user", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user: { id: "u1", email: "a", role: "user" } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = spy as unknown as typeof fetch;

    const user = await login({ email: "a", password: "p", persistent: true });
    expect(user.id).toBe("u1");

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/login");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      email: "a",
      password: "p",
      persistent: true,
    });
  });

  it("logout POSTs and resolves on 204", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;

    await expect(logout()).resolves.toBeNull();
  });
});
