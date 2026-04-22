import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { MustChangePasswordGate } from "./MustChangePasswordGate";
import { AuthProvider, useAuth } from "../auth/AuthContext";

function Probe() {
  const { setMustChangePassword } = useAuth();
  return (
    <div>
      <button onClick={() => setMustChangePassword(true)}>trigger</button>
      <span>outlet-content</span>
    </div>
  );
}

describe("MustChangePasswordGate", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders outlet when flag is false", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user_id: "u1", email: "a", is_admin: false }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    render(
      <MemoryRouter>
        <AuthProvider>
          <Routes>
            <Route element={<MustChangePasswordGate />}>
              <Route path="/" element={<Probe />} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("outlet-content")).toBeTruthy(),
    );
  });

  it("renders the change-password form when flag is true", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user_id: "u1", email: "a", is_admin: false }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    function TriggerGate() {
      const { setMustChangePassword } = useAuth();
      setMustChangePassword(true);
      return null;
    }

    render(
      <MemoryRouter>
        <AuthProvider>
          <TriggerGate />
          <Routes>
            <Route element={<MustChangePasswordGate />}>
              <Route path="/" element={<Probe />} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /set password/i })).toBeTruthy(),
    );
  });
});
