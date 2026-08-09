import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as settings from "../../../api/settings";
import { ModelPicker } from "../ModelPicker";

afterEach(() => {
  vi.restoreAllMocks();
});

const MODELS = [
  { id: "m1", provider_kind: "openai", model_ref: "gpt-5.4", display_name: "GPT-5.4", provider_id: "p1", is_enabled: true },
  { id: "m2", provider_kind: "openai", model_ref: "gpt-5.5", display_name: "GPT-5.5", provider_id: "p1", is_enabled: true },
];

describe("ModelPicker persist-on-load", () => {
  it("persists the first enabled model when no preference is saved", async () => {
    vi.spyOn(settings, "getEnabledModels").mockResolvedValue(MODELS as never);
    vi.spyOn(settings, "getPrefs").mockResolvedValue({ preferred_model_id: null } as never);
    const update = vi.spyOn(settings, "updatePrefs").mockResolvedValue({} as never);

    render(<ModelPicker />);

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith({ preferred_model_id: "m1" }),
    );
  });

  it("does not overwrite an existing valid preference", async () => {
    vi.spyOn(settings, "getEnabledModels").mockResolvedValue(MODELS as never);
    vi.spyOn(settings, "getPrefs").mockResolvedValue({ preferred_model_id: "m2" } as never);
    const update = vi.spyOn(settings, "updatePrefs").mockResolvedValue({} as never);

    render(<ModelPicker />);

    // Wait until the saved selection has rendered, proving the load effect ran.
    await screen.findByText("GPT-5.5");
    expect(update).not.toHaveBeenCalled();
  });
});
