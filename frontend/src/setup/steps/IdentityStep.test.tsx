import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IdentityStep } from "./IdentityStep";

describe("IdentityStep", () => {
  it("disables Next when display name is empty", () => {
    render(<IdentityStep onBack={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("posts display name and calls onSaved", async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ display_name: "TK" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<IdentityStep onBack={vi.fn()} onSaved={onSaved} />);
    await userEvent.type(screen.getByLabelText(/display name/i), "TK");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });
});
