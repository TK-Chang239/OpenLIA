import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

function wrap(initialRoute: string) {
  return (
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>Login page</p>} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <p>Protected content</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("redirects to /login when unauthenticated", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;

    render(wrap("/"));

    await waitFor(() =>
      expect(screen.getByText("Login page")).toBeInTheDocument(),
    );
  });

  it("renders children when authenticated", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user: { id: "u1", email: "a", role: "admin" } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    render(wrap("/"));

    await waitFor(() =>
      expect(screen.getByText("Protected content")).toBeInTheDocument(),
    );
  });

  it("renders children in personal mode (404 from /auth/session)", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 404 })) as unknown as typeof fetch;

    render(wrap("/"));

    await waitFor(() =>
      expect(screen.getByText("Protected content")).toBeInTheDocument(),
    );
  });
});
