import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelsStep } from "./ModelsStep";

describe("ModelsStep", () => {
  it("disables Next when any required tier has no entries", () => {
    render(
      <ModelsStep
        totalSteps={5}
        requiredTiers={["thinking", "everyday", "quick"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("enables Next after adding a model in each required tier", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ok: true, latency_ms: 42, error: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    render(
      <ModelsStep
        totalSteps={5}
        requiredTiers={["thinking", "everyday", "quick"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    for (const tier of ["thinking", "everyday", "quick"]) {
      const section = screen.getByTestId(`tier-${tier}`);
      await userEvent.click(section.querySelector("button[data-test=add]")!);
      await userEvent.type(section.querySelector("input[name=model]")!, "gpt-5.4");
      await userEvent.type(section.querySelector("input[name=api_key]")!, "sk-test");
      await userEvent.click(section.querySelector("button[data-test=test]")!);
    }
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeEnabled(),
    );
  });
});
