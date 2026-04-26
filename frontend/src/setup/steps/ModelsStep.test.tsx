import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModelsStep } from "./ModelsStep";

describe("ModelsStep", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("starts on the keys screen with Next disabled until a key is added", async () => {
    render(
      <ModelsStep
        totalSteps={5}
        requiredTiers={["thinking", "everyday", "quick"]}
        onBack={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();

    await userEvent.type(
      screen.getByPlaceholderText(/Label/i),
      "My OpenAI",
    );
    await userEvent.type(screen.getByPlaceholderText(/^API key$/i), "sk-test");
    await userEvent.click(screen.getByText(/Save key/i));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeEnabled(),
    );
  });

  it("on the tiers screen, Next is gated on at least one green entry per required tier", async () => {
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

    // Add one key on screen 1.
    await userEvent.type(screen.getByPlaceholderText(/Label/i), "My OpenAI");
    await userEvent.type(screen.getByPlaceholderText(/^API key$/i), "sk-test");
    await userEvent.click(screen.getByText(/Save key/i));
    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    // Now on screen 2: add a model in each required tier.
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
    for (const tier of ["thinking", "everyday", "quick"]) {
      const section = screen.getByTestId(`tier-${tier}`);
      await userEvent.click(section.querySelector("button[data-test=add]")!);
      await userEvent.type(section.querySelector("input[name=model]")!, "gpt-4o");
      await userEvent.click(section.querySelector("button[data-test=test]")!);
    }
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /next/i })).toBeEnabled(),
    );
  });
});
