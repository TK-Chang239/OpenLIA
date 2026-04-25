import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { AuthProvider } from "../auth/AuthContext";

describe("LoginPage", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders LoginForm under AuthLayout when unauthenticated", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;

    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("LIA")).toBeTruthy());
    expect(screen.getByRole("button", { name: /log in/i })).toBeTruthy();
  });

  it("redirects to ?next= on successful login", async () => {
    let sessionCalls = 0;
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (typeof url === "string" && url.includes("/auth/signup-policy")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ mode: "invite_only", invite_required: true }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (
        typeof url === "string" &&
        url.includes("/auth/login") &&
        init?.method === "POST"
      ) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              user_id: "u1",
              email: "a@x.com",
              display_name: "A",
              is_admin: false,
              must_change_password: false,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (typeof url === "string" && url.includes("/auth/session")) {
        sessionCalls += 1;
        if (sessionCalls === 1) {
          return Promise.resolve(new Response(null, { status: 401 }));
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              user_id: "u1",
              email: "a@x.com",
              display_name: "A",
              is_admin: false,
              must_change_password: false,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(new Response(null, { status: 401 }));
    }) as unknown as typeof fetch;

    render(
      <MemoryRouter initialEntries={["/login?next=/secretary"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/secretary"
              element={<div data-testid="secretary-page">SECRETARY</div>}
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByLabelText("Email")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() =>
      expect(screen.queryByTestId("secretary-page")).not.toBeNull(),
    );
  });

  it("hides sign-up link when policy mode resolves to closed", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (typeof url === "string" && url.includes("/auth/signup-policy")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ mode: "closed", invite_required: false }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(new Response(null, { status: 401 }));
    }) as unknown as typeof fetch;

    render(
      <MemoryRouter initialEntries={["/login?invite=tok_abcdefgh"]}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    // Wait for policy fetch + render to settle
    await waitFor(() => expect(screen.getByLabelText("Email")).toBeTruthy());
    // Allow microtasks to flush so signup policy applies
    await waitFor(() => expect(screen.queryByText(/sign up/i)).toBeNull());
  });

});
