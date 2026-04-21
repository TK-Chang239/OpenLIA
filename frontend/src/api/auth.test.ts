import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getSession,
  login,
  logout,
  register,
  getSignupPolicy,
  requestPasswordReset,
  consumePasswordReset,
  changePassword,
  logoutAll,
} from "./auth";
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

    const result = await login({ email: "a", password: "p", persistent: true });
    expect(result.user.id).toBe("u1");

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

  it("login surfaces must_change_password flag", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user: { id: "u1", email: "a", role: "user" },
          must_change_password: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const result = await login({ email: "a", password: "p", persistent: false });
    expect(result.user.id).toBe("u1");
    expect(result.must_change_password).toBe(true);
  });

  it("register posts invite + credentials", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user: { id: "u2", email: "b", role: "user" },
          must_change_password: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    global.fetch = spy as unknown as typeof fetch;

    const result = await register({
      email: "b@x.com",
      password: "pw12345!",
      display_name: "B",
      invite_token: "tok_abc",
    });

    expect(result.user.email).toBe("b");
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/register");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      email: "b@x.com",
      password: "pw12345!",
      display_name: "B",
      invite_token: "tok_abc",
    });
  });

  it("getSignupPolicy returns mode + invite_required", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ mode: "invite_only", invite_required: true }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const policy = await getSignupPolicy();
    expect(policy.invite_required).toBe(true);
    expect(policy.mode).toBe("invite_only");
  });

  it("requestPasswordReset always resolves (neutral 200)", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    ) as unknown as typeof fetch;

    await expect(requestPasswordReset("a@x.com")).resolves.toBeNull();
  });

  it("consumePasswordReset posts token + new password", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await consumePasswordReset({ token: "t", new_password: "newpw123!" });

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/password-reset/consume");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      token: "t",
      new_password: "newpw123!",
    });
  });

  it("changePassword posts current + new password", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await changePassword({ current_password: "a", new_password: "b" });

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/change-password");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      current_password: "a",
      new_password: "b",
    });
  });

  it("logoutAll POSTs /logout-all", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await expect(logoutAll()).resolves.toBeNull();
    expect(spy.mock.calls[0][0]).toBe("/api/auth/logout-all");
  });
});
