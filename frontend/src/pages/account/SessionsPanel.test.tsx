import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SessionsPanel } from "./SessionsPanel";

describe("SessionsPanel", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the current-session line and the sign-out-all button", () => {
    render(<SessionsPanel />);
    expect(screen.getByText(/signed in on this device/i)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /sign out all other devices/i }),
    ).toBeTruthy();
  });

  it("POSTs /auth/logout-all on click and shows success", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    render(<SessionsPanel />);
    fireEvent.click(
      screen.getByRole("button", { name: /sign out all other devices/i }),
    );

    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toMatch(
        /other sessions signed out/i,
      ),
    );
    expect(spy.mock.calls[0][0]).toBe("/api/auth/logout-all");
  });
});
