import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RegisterModelsScreen } from "../RegisterModelsScreen";
import type { ApiKey } from "../KeysScreen";
import type { ModelEntry } from "../RegisterModelsScreen";

const keys: ApiKey[] = [
  { id: "k1", label: "My OpenAI", api_key: "sk-test" },
  { id: "k2", label: "My Anthropic", api_key: "sk-ant-test" },
];

describe("RegisterModelsScreen", () => {
  it("adding a model calls onChange with the new entry", async () => {
    const onChange = vi.fn();
    render(
      <RegisterModelsScreen
        totalSteps={5}
        keys={keys}
        entries={[]}
        onChange={onChange}
        onBack={vi.fn()}
        onNext={vi.fn()}
      />,
    );

    const card = screen.getByTestId("register-card-k1");
    await userEvent.click(within(card).getByRole("button", { name: /add model/i }));
    await userEvent.type(
      within(card).getByPlaceholderText(/model id/i),
      "gpt-5.4-pro",
    );
    await userEvent.type(
      within(card).getByPlaceholderText(/display name/i),
      "GPT 5.4 Pro",
    );
    await userEvent.click(within(card).getByRole("button", { name: /^save$/i }));

    expect(onChange).toHaveBeenCalled();
    const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as ModelEntry[];
    expect(last).toHaveLength(1);
    expect(last[0]).toMatchObject({
      key_id: "k1",
      model_ref: "gpt-5.4-pro",
      display_name: "GPT 5.4 Pro",
    });
  });

  it("removing a model calls onChange minus that entry", async () => {
    const entries: ModelEntry[] = [
      { key_id: "k1", model_ref: "gpt-5.4-pro", display_name: "GPT 5.4 Pro" },
      { key_id: "k1", model_ref: "gpt-5.4-mini", display_name: "GPT 5.4 Mini" },
    ];
    const onChange = vi.fn();
    render(
      <RegisterModelsScreen
        totalSteps={5}
        keys={keys}
        entries={entries}
        onChange={onChange}
        onBack={vi.fn()}
        onNext={vi.fn()}
      />,
    );

    const removeButtons = screen.getAllByRole("button", { name: /remove model/i });
    await userEvent.click(removeButtons[0]);

    expect(onChange).toHaveBeenCalledWith([
      { key_id: "k1", model_ref: "gpt-5.4-mini", display_name: "GPT 5.4 Mini" },
    ]);
  });

  it("Next is disabled until at least one model is entered", () => {
    const { rerender } = render(
      <RegisterModelsScreen
        totalSteps={5}
        keys={keys}
        entries={[]}
        onChange={vi.fn()}
        onBack={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();

    rerender(
      <RegisterModelsScreen
        totalSteps={5}
        keys={keys}
        entries={[
          { key_id: "k1", model_ref: "gpt-5.4-pro", display_name: "GPT 5.4 Pro" },
        ]}
        onChange={vi.fn()}
        onBack={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
  });
});
