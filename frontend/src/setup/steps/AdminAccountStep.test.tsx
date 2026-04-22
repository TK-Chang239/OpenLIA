import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminAccountStep } from "./AdminAccountStep";

describe("AdminAccountStep", () => {
  it("disables Next until all fields valid and passwords match", async () => {
    render(<AdminAccountStep onBack={vi.fn()} onSaved={vi.fn()} />);
    const next = screen.getByRole("button", { name: /next/i });
    expect(next).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/email/i), "boss@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "CorrectHorseBattery9!");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "CorrectHorseBattery9!");
    await userEvent.type(screen.getByLabelText(/display name/i), "Boss");
    expect(next).toBeEnabled();
  });

  it("shows mismatch error when passwords differ", async () => {
    render(<AdminAccountStep onBack={vi.fn()} onSaved={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/^password$/i), "CorrectHorseBattery9!");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different");
    expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument();
  });

  it("posts payload and calls onSaved", async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ email: "boss@example.com" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<AdminAccountStep onBack={vi.fn()} onSaved={onSaved} />);
    await userEvent.type(screen.getByLabelText(/email/i), "boss@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "CorrectHorseBattery9!");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "CorrectHorseBattery9!");
    await userEvent.type(screen.getByLabelText(/display name/i), "Boss");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });
});
