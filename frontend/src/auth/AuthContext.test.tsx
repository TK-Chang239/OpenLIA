import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, renderHook } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthContext";
import { ApiError } from "../api/client";

function Probe() {
  const { status, user } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user-id">{user?.id ?? ""}</span>
    </div>
  );
}

describe("AuthProvider", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("200 → authenticated with user", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user_id: "u1", email: "a", is_admin: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );
    expect(screen.getByTestId("user-id").textContent).toBe("u1");
  });

  it("401 → unauthenticated", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
    expect(screen.getByTestId("user-id").textContent).toBe("");
  });

  it("404 → personal mode with synthetic local user", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 404 })) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("personal"),
    );
    expect(screen.getByTestId("user-id").textContent).toBe("local");
  });

  it("throws when useAuth is called outside of a provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Probe />)).toThrow(/useAuth must be used inside AuthProvider/);
    spy.mockRestore();
  });

  it("login() updates state to authenticated after success", async () => {
    const fetchMock = vi
      .fn()
      // Initial getSession → 401
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      // login() → 200
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user_id: "u2", email: "b", is_admin: false }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    global.fetch = fetchMock as unknown as typeof fetch;

    function ProbeWithButton() {
      const { status, login } = useAuth();
      return (
        <div>
          <span data-testid="status">{status}</span>
          <button
            onClick={() => {
              void login({ email: "b", password: "p", persistent: false });
            }}
          >
            go
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <ProbeWithButton />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );

    await act(async () => {
      screen.getByRole("button", { name: "go" }).click();
    });

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );
  });

  it("treats unexpected ApiError like unauthenticated", async () => {
    global.fetch = vi.fn().mockRejectedValue(new ApiError(500, "boom")) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
  });

  it("exposes mustChangePassword: false by default after session fetch", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user_id: "u1", email: "a", is_admin: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(result.current.mustChangePassword).toBe(false);
  });

  it("login() sets mustChangePassword from server response", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            email: "a",
            is_admin: false,
            must_change_password: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => expect(result.current.status).toBe("unauthenticated"));

    await act(async () => {
      await result.current.login({
        email: "a",
        password: "p",
        persistent: false,
      });
    });

    expect(result.current.status).toBe("authenticated");
    expect(result.current.mustChangePassword).toBe(true);
  });

  it("logout() then refresh() on 401 clears mustChangePassword", async () => {
    let callIdx = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      callIdx += 1;
      // 1st call: initial getSession returns must_change_password=true
      if (callIdx === 1) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              user_id: "u1",
              email: "a@x.com",
              is_admin: false,
              must_change_password: true,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      // 2nd call: logout returns 204
      if (callIdx === 2) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      // Subsequent: getSession returns 401
      return Promise.resolve(new Response(null, { status: 401 }));
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(result.current.mustChangePassword).toBe(true);

    await act(async () => {
      await result.current.logout();
    });
    expect(result.current.mustChangePassword).toBe(false);
    expect(result.current.status).toBe("unauthenticated");

    // Now an explicit refresh resolving 401 keeps the flag cleared.
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.mustChangePassword).toBe(false);
    expect(result.current.status).toBe("unauthenticated");
  });

  it("clearMustChangePassword() resets the flag", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user_id: "u1", email: "a", is_admin: false }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    act(() => {
      result.current.setMustChangePassword(true);
    });
    expect(result.current.mustChangePassword).toBe(true);

    act(() => {
      result.current.clearMustChangePassword();
    });
    expect(result.current.mustChangePassword).toBe(false);
  });
});
