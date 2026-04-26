import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccessControlStep } from "./AccessControlStep";

describe("AccessControlStep", () => {
  it("posts policy + bind host/port", async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<AccessControlStep onBack={vi.fn()} onSaved={onSaved} />);
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("disables the 'open signup' option (v2 only)", () => {
    render(<AccessControlStep onBack={vi.fn()} onSaved={vi.fn()} />);
    const open = screen.getByRole("radio", { name: /open signup/i });
    expect(open).toBeDisabled();
  });

  it("restores policy and bind fields on remount after Next", async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const first = render(<AccessControlStep onBack={vi.fn()} onSaved={onSaved} />);
    await userEvent.click(screen.getByRole("radio", { name: /closed/i }));
    const domains = screen.getByPlaceholderText(/example\.com/i);
    await userEvent.type(domains, "acme.com");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    first.unmount();

    render(<AccessControlStep onBack={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByRole("radio", { name: /closed/i })).toBeChecked();
    expect(screen.getByPlaceholderText(/example\.com/i)).toHaveValue("acme.com");
  });
});
