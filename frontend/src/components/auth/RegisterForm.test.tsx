import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RegisterForm } from "./RegisterForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderForm(inviteToken = "tok_xyz") {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <RegisterForm inviteToken={inviteToken} />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("RegisterForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("rejects mismatched passwords before submitting", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderForm();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
  });

  it("surfaces invite_invalid as banner", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "invite_invalid",
            message: "This invite link is no longer valid. Contact your administrator for a new one.",
          }),
          { status: 403, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    renderForm();

    // Wait for auth to settle (session probe resolves)
    await waitFor(() =>
      expect(screen.getByLabelText("Email")).toBeTruthy(),
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/no longer valid/),
    );
  });
});
