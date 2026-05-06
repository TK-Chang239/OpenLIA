import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { ModelPicker } from "../ModelPicker";

vi.mock("../../../api/department-model-pref", () => ({
  getDepartmentModelPref: vi.fn(),
  setDepartmentModelPref: vi.fn(),
}));

vi.mock("../../../api/settings", () => ({
  getModelsRoster: vi.fn(),
}));

import {
  getDepartmentModelPref,
  setDepartmentModelPref,
} from "../../../api/department-model-pref";
import { getModelsRoster, type ModelsRoster } from "../../../api/settings";

const ROSTER: ModelsRoster = {
  thinking: [
    {
      id: "opus",
      provider_id: "p1",
      provider_kind: "anthropic",
      model_ref: "claude-opus-4",
      display_name: "Opus",
      is_tier_default: true,
      is_enabled: true,
    },
  ],
  everyday: [
    {
      id: "sonnet",
      provider_id: "p1",
      provider_kind: "anthropic",
      model_ref: "claude-sonnet-4",
      display_name: "Sonnet",
      is_tier_default: true,
      is_enabled: true,
    },
  ],
  quick: [],
};

describe("ModelPicker", () => {
  beforeEach(() => {
    vi.mocked(getModelsRoster).mockResolvedValue(ROSTER);
    vi.mocked(setDepartmentModelPref).mockResolvedValue({
      department_id: "morning_briefing",
      model_id: "opus",
      effective_model_id: "opus",
    });
  });

  it("shows the user's explicit pref selected when set", async () => {
    vi.mocked(getDepartmentModelPref).mockResolvedValue({
      department_id: "morning_briefing",
      model_id: "opus",
      effective_model_id: "opus",
    });

    render(<ModelPicker departmentSlug="morning-briefing" />);

    const select = (await screen.findByTestId(
      "mb-model-picker",
    )) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe("opus"));
  });

  it("falls back to effective_model_id when no override is set", async () => {
    vi.mocked(getDepartmentModelPref).mockResolvedValue({
      department_id: "morning_briefing",
      model_id: null,
      effective_model_id: "sonnet",
    });

    render(<ModelPicker departmentSlug="morning-briefing" />);

    const select = (await screen.findByTestId(
      "mb-model-picker",
    )) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe("sonnet"));
  });
});
