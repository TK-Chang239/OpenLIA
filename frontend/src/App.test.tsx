import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter } from "react-router-dom";
import App from "./App";
import { routes } from "./router/routes";

describe("App", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    const sessionOk = new Response(
      JSON.stringify({ user_id: "u1", email: "a", is_admin: true }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    const unreadOk = new Response(
      JSON.stringify({ total: 0, by_department: {} }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    global.fetch = vi
      .fn()
      .mockImplementation((input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes("/auth/session")) return Promise.resolve(sessionOk.clone());
        if (url.includes("/notifications/unread"))
          return Promise.resolve(unreadOk.clone());
        return Promise.resolve(new Response(null, { status: 204 }));
      }) as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("boots with the Sidebar visible when authenticated", async () => {
    const router = createMemoryRouter(routes, { initialEntries: ["/secretary"] });
    render(<App router={router} />);
    await waitFor(() => {
      expect(
        screen.getByRole("navigation", { name: /main navigation/i }),
      ).toBeInTheDocument();
    });
  });
});
