import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SessionsPanel } from "./SessionsPanel";
import { AuthProvider } from "../../auth/AuthContext";

function renderPanel() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SessionsPanel />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("SessionsPanel", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("calls logout-all when the button is clicked", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // AuthProvider session probe
      .mockResolvedValueOnce(new Response(null, { status: 204 })) // logout-all
      .mockResolvedValueOnce(new Response(null, { status: 204 })); // logout
    global.fetch = fetchMock as unknown as typeof fetch;
    renderPanel();
    fireEvent.click(
      await screen.findByRole("button", { name: /sign out of all devices/i }),
    );
    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      expect(calls.some((c) => String(c[0]).includes("/api/auth/logout-all"))).toBe(true);
    });
  });
});
