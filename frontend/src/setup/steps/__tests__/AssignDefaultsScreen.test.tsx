import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AssignDefaultsScreen } from "../AssignDefaultsScreen";
import type { ModelEntry } from "../RegisterModelsScreen";

const registered: ModelEntry[] = [
  { key_id: "k1", model_ref: "gpt-5.4-pro", display_name: "GPT 5.4 Pro" },
  { key_id: "k1", model_ref: "gpt-5.4-mini", display_name: "GPT 5.4 Mini" },
];

const depts = ["equity_research", "morning_briefing"];
const roles = ["chat", "classifier"];

describe("AssignDefaultsScreen", () => {
  it("renders every department and every system role", () => {
    render(
      <AssignDefaultsScreen
        totalSteps={5}
        enabledDepartmentIds={depts}
        systemRoleIds={roles}
        registeredModels={registered}
        onBack={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByLabelText(/equity research/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/morning briefing/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^chat$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/classifier/i)).toBeInTheDocument();
  });

  it("submit fires onSubmit with the selected values", async () => {
    const onSubmit = vi.fn();
    render(
      <AssignDefaultsScreen
        totalSteps={5}
        enabledDepartmentIds={depts}
        systemRoleIds={roles}
        registeredModels={registered}
        onBack={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await userEvent.selectOptions(screen.getByLabelText(/equity research/i), "gpt-5.4-pro");
    await userEvent.selectOptions(screen.getByLabelText(/morning briefing/i), "gpt-5.4-mini");
    await userEvent.selectOptions(screen.getByLabelText(/^chat$/i), "gpt-5.4-pro");
    await userEvent.selectOptions(screen.getByLabelText(/classifier/i), "gpt-5.4-mini");

    await userEvent.click(screen.getByRole("button", { name: /finish|next|save/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      department_defaults: {
        equity_research: "gpt-5.4-pro",
        morning_briefing: "gpt-5.4-mini",
      },
      system_role_defaults: {
        chat: "gpt-5.4-pro",
        classifier: "gpt-5.4-mini",
      },
    });
  });

  it("submit is disabled when no model selected for at least one slot", async () => {
    const onSubmit = vi.fn();
    render(
      <AssignDefaultsScreen
        totalSteps={5}
        enabledDepartmentIds={depts}
        systemRoleIds={roles}
        registeredModels={registered}
        onBack={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole("button", { name: /finish|next|save/i })).toBeDisabled();

    // Fill only one slot, remaining still empty -> still disabled.
    await userEvent.selectOptions(screen.getByLabelText(/equity research/i), "gpt-5.4-pro");
    expect(screen.getByRole("button", { name: /finish|next|save/i })).toBeDisabled();
  });
});
