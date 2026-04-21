import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "./Sidebar";

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders every core and department link with its accessible name", async () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /repository/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /secretary/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /equity research/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /panic thermometer/i })).toBeInTheDocument();
  });

  it("toggles collapsed state via the toggle button", async () => {
    renderAt("/");
    const toggle = screen.getByRole("button", { name: /collapse sidebar/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await act(async () => {
      toggle.click();
    });
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /expand sidebar/i }),
      ).toHaveAttribute("aria-expanded", "false"),
    );
  });

  it("shows an unread dot on the department with a positive count", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 1, by_department: { morning_briefing: 1 } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    renderAt("/");
    await waitFor(() => {
      const link = screen.getByRole("link", { name: /morning briefing/i });
      expect(link.querySelector('[data-testid="nav-item-dot"]')).not.toBeNull();
    });
  });
});
