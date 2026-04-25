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

  it("wires aria-describedby on confirm when mismatched", async () => {
    render(<ChangePasswordForm />);
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "oldpw123" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Different!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Confirm New Password") as HTMLInputElement).getAttribute(
          "aria-describedby",
        ),
      ).toBe("account_confirm_password-error"),
    );
  });

  it("renders offline banner on TypeError", async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch")) as unknown as typeof fetch;
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
      expect(screen.getByRole("alert").textContent).toMatch(
        /Can't reach the server/,
      ),
    );
  });

  it("toggles aria-busy on submit during request", async () => {
    let resolveCall: (resp: Response) => void = () => undefined;
    global.fetch = vi.fn().mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveCall = resolve;
        }),
    ) as unknown as typeof fetch;
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
    const button = screen.getByRole("button", { name: /change password/i });
    fireEvent.click(button);
    await waitFor(() =>
      expect(button.getAttribute("aria-busy")).toBe("true"),
    );
    resolveCall(new Response(null, { status: 204 }));
    await waitFor(() =>
      expect(button.getAttribute("aria-busy")).toBe("false"),
    );
  });
});
