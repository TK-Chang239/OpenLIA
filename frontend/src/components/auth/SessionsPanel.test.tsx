import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SessionsPanel } from "./SessionsPanel";
import { AuthProvider } from "../../auth/AuthContext";

const SESSIONS = [
  {
    id: "cur",
    created_at: "2026-08-09T10:00:00Z",
    last_seen_at: "2026-08-09T12:00:00Z",
    expires_at: "2026-09-09T10:00:00Z",
    user_agent: "Chrome on macOS",
    ip_address: "10.0.0.1",
    current: true,
  },
  {
    id: "other",
    created_at: "2026-08-01T10:00:00Z",
    last_seen_at: "2026-08-08T09:00:00Z",
    expires_at: "2026-09-01T10:00:00Z",
    user_agent: "Safari on iPhone",
    ip_address: "10.0.0.2",
    current: false,
  },
];

/** URL/method-routing fetch stub so call order does not matter. */
function installFetch() {
  const calls: { url: string; method: string }[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    calls.push({ url, method });
    if (url.includes("/api/auth/sessions") && method === "DELETE") {
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    if (url.includes("/api/auth/sessions") && method === "GET") {
      return Promise.resolve(
        new Response(JSON.stringify({ sessions: SESSIONS }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (url.includes("/api/auth/logout-all")) {
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    if (url.includes("/api/auth/logout")) {
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    // AuthProvider session probe (singular) -> unauthenticated.
    return Promise.resolve(new Response(null, { status: 401 }));
  });
  global.fetch = fetchMock as unknown as typeof fetch;
  return { fetchMock, calls };
}

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

  it("lists active sessions and flags the current device", async () => {
    installFetch();
    renderPanel();
    expect(await screen.findByText("Chrome on macOS")).toBeInTheDocument();
    expect(screen.getByText("Safari on iPhone")).toBeInTheDocument();
    expect(screen.getByText(/this device/i)).toBeInTheDocument();
    // Only the non-current session exposes a per-session Sign out button.
    expect(screen.getAllByRole("button", { name: /^sign out$/i })).toHaveLength(1);
  });

  it("revokes a single session via DELETE", async () => {
    const { calls } = installFetch();
    renderPanel();
    await screen.findByText("Safari on iPhone");
    fireEvent.click(screen.getByRole("button", { name: /^sign out$/i }));
    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.method === "DELETE" && c.url.includes("/api/auth/sessions/other"),
        ),
      ).toBe(true),
    );
  });

  it("calls logout-all when the sign-out-all button is clicked", async () => {
    const { calls } = installFetch();
    renderPanel();
    fireEvent.click(
      await screen.findByRole("button", { name: /sign out of all devices/i }),
    );
    await waitFor(() =>
      expect(calls.some((c) => c.url.includes("/api/auth/logout-all"))).toBe(true),
    );
  });
});
