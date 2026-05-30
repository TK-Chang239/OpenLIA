import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as settings from "../../../api/settings";
import { EuModelPicker } from "../EuModelPicker";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("EuModelPicker", () => {
  it("emits the first enabled model on load", async () => {
    vi.spyOn(settings, "getEnabledModels").mockResolvedValue([
      { id: "m1", provider_kind: "anthropic", model_ref: "claude-sonnet-4-6", display_name: "Claude Sonnet 4.6", is_enabled: true } as never,
    ]);
    const onChange = vi.fn();
    render(<EuModelPicker onChange={onChange} />);
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ provider_kind: "anthropic", model: "claude-sonnet-4-6" })));
  });
});
