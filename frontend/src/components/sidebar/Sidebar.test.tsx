import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { AuthProvider } from "../../auth/AuthContext";
import { useDeptHealth } from "../../store/dept-health";

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <Sidebar />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = input.toString();
      if (url.includes("/auth/session")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ user_id: "u1", email: "a", is_admin: true }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ total: 0, by_department: {} }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    }) as unknown as typeof fetch;
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

  it("calls signOut when the sign-out button is clicked", async () => {
    const spy = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = input.toString();
      if (url.includes("/auth/session")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ user_id: "u1", email: "a", is_admin: true }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(new Response(null, { status: 204 }));
    });
    global.fetch = spy as unknown as typeof fetch;

    renderAt("/");

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /sign out/i })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));

    await waitFor(() => {
      const urls = (spy.mock.calls as [string][]).map((c) => c[0]);
      expect(urls).toContain("/api/auth/logout");
    });
  });

  it("renders at 220px expanded width by default", () => {
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: /main navigation/i });
    expect(nav.className).toContain("w-[220px]");
  });

  it("collapses to 52px when toggle clicked", async () => {
    renderAt("/");
    const toggle = screen.getByRole("button", { name: /collapse sidebar/i });
    await act(async () => {
      toggle.click();
    });
    await waitFor(() => {
      const nav = screen.getByRole("navigation", { name: /main navigation/i });
      expect(nav.className).toContain("w-[52px]");
    });
  });

  it("mutes a disabled dept link and exposes the reason as tooltip title", () => {
    useDeptHealth.setState({
      healths: {
        macro_research: {
          department_id: "macro_research",
          status: "disabled",
          reason: "Missing required categories: financial",
          missing_categories: ["financial"],
          unresolved_needs: [],
        },
      },
      loaded: true,
      loading: false,
      error: null,
    });
    renderAt("/");
    const link = screen.getByRole("link", { name: /macro research/i });
    expect(link.className).toContain("opacity-50");
    expect(link).toHaveAttribute(
      "title",
      "Missing required categories: financial",
    );
    // Reset for unrelated tests.
    useDeptHealth.setState({ healths: {}, loaded: false, loading: false, error: null });
  });

  it("is hidden below md breakpoint via tailwind classes", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    renderAt("/");
    const nav = screen.getByRole("navigation", { name: /main navigation/i });
    expect(nav.className).toContain("hidden");
    expect(nav.className).toContain("md:flex");

    window.matchMedia = originalMatchMedia;
  });
});
