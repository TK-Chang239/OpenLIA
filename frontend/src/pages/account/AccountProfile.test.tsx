import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AccountProfile } from "./AccountProfile";
import { AuthProvider } from "../../auth/AuthContext";

describe("AccountProfile", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders email + role for authenticated user", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user_id: "u1",
          email: "x@y.com",
          is_admin: true,
          display_name: "Alice",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <AccountProfile />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("x@y.com")).toBeTruthy());
    expect(screen.getByText("Alice")).toBeTruthy();
    expect(screen.getByText(/admin/i)).toBeTruthy();
  });
});
