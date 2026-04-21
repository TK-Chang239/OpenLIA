import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChangePasswordForm } from "./ChangePasswordForm";

describe("ChangePasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("requires all three fields", () => {
    render(<ChangePasswordForm />);
    expect(
      (
        screen.getByRole("button", { name: /change password/i }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it("shows success banner on 204", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;
    render(<ChangePasswordForm />);
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "oldpw123" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toMatch(/updated/i),
    );
  });

  it("surfaces invalid_credentials on 401 as field error", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "invalid_credentials",
          message: "Current password is incorrect.",
          field: "current_password",
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    render(<ChangePasswordForm />);
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "wrong" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByText(/Current password is incorrect/i)).toBeTruthy(),
    );
  });
});
