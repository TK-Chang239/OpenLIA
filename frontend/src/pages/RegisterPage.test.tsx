import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RegisterPage } from "./RegisterPage";
import { AuthProvider } from "../auth/AuthContext";

describe("RegisterPage", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("redirects when no invite param", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/register"]}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.queryByLabelText("Confirm Password")).toBeNull();
  });

  it("renders RegisterForm with invite param", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (typeof url === "string" && url.includes("/auth/signup-policy")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ mode: "invite_only", invite_required: true }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(new Response(null, { status: 401 }));
    }) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/register?invite=tok_abcdefgh"]}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Confirm Password")).toBeTruthy(),
    );
  });

  it("shows closed banner instead of form when policy is closed", async () => {
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
      <MemoryRouter initialEntries={["/register?invite=tok_abc"]}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(
        /Registration is closed/,
      ),
    );
    expect(screen.queryByLabelText("Confirm Password")).toBeNull();
    expect(screen.getByText(/Back to Log In/)).toBeTruthy();
  });
});
