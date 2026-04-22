import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModeStep } from "./ModeStep";

describe("ModeStep", () => {
  it("disables Next until a card is selected", () => {
    render(<ModeStep envLocked={false} initialMode={null} onSaved={vi.fn()} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("saves and advances on Next when Personal is picked", async () => {
    const onSaved = vi.fn();
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ mode: "personal" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    render(<ModeStep envLocked={false} initialMode={null} onSaved={onSaved} />);
    await userEvent.click(screen.getByRole("button", { name: /^personal$/i }));
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith("personal"));
    expect(fetchSpy).toHaveBeenCalled();
  });

  it("shows from-environment badge when envLocked", () => {
    render(<ModeStep envLocked={true} initialMode="company" onSaved={vi.fn()} />);
    expect(screen.getByText(/from environment/i)).toBeInTheDocument();
  });
});
