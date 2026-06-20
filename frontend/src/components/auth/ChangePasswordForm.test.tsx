import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChangePasswordForm } from "./ChangePasswordForm";

function renderForm() {
  return render(<ChangePasswordForm />);
}

describe("ChangePasswordForm", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("blocks submit when confirm does not match", async () => {
    global.fetch = vi.fn() as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "OldPass1!" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Different1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
    expect((global.fetch as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBe(0);
  });

  it("posts to change-password and shows success on 204", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "OldPass1!" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByText(/password changed/i)).toBeTruthy(),
    );
    const call = (global.fetch as unknown as { mock: { calls: [string][] } }).mock.calls[0];
    expect(call[0]).toContain("/api/auth/change-password");
  });
});
