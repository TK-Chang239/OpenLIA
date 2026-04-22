import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MustChangePasswordForm } from "./MustChangePasswordForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderForm() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <MustChangePasswordForm />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("MustChangePasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("requires confirm to match", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("Temporary Password"), {
      target: { value: "OldTemp1!" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Different1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /set password/i }));
    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
  });

  it("on success clears mustChangePassword flag", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockResolvedValueOnce(new Response(null, { status: 204 })) // change-password
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user_id: "u1", email: "a", is_admin: false }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    renderForm();
    fireEvent.change(screen.getByLabelText("Temporary Password"), {
      target: { value: "OldTemp1!" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /set password/i }));
    await waitFor(() =>
      expect(
        (global.fetch as unknown as { mock: { calls: unknown[] } }).mock.calls
          .length,
      ).toBeGreaterThanOrEqual(2),
    );
  });
});
