import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ResetPasswordForm } from "./ResetPasswordForm";

function renderForm(token = "t-1") {
  return render(
    <MemoryRouter>
      <ResetPasswordForm token={token} />
    </MemoryRouter>,
  );
}

describe("ResetPasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows confirm-mismatch error before submit", async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Different1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
  });

  it("shows success banner on 204 and renders back link", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toMatch(/password updated/i),
    );
  });

  it("surfaces token_invalid as error banner with no form", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "token_invalid",
          message:
            "This reset link has expired or has already been used. Contact your administrator for a new one.",
        }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/expired or has already been used/i),
    );
  });
});
