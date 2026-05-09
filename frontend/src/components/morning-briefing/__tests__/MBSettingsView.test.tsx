import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MbConfig } from "../../../api/morning-briefing";
import { MBSettingsView } from "../MBSettingsView";

const baseConfig: MbConfig = {
  report_length: "normal",
  enabled_section_ids: [],
  section_topics: {},
  custom_sections: [],
  reference_portfolio: false,
};

beforeEach(() => {
  vi.stubGlobal("crypto", {
    ...globalThis.crypto,
    randomUUID: () => "uuid-fixed-1",
  });
});

describe("MBSettingsView", () => {
  it("toggling a section updates enabled_section_ids on save", async () => {
    const onSaveConfig = vi
      .fn()
      .mockImplementation(async (cfg: MbConfig) => cfg);
    render(
      <MBSettingsView
        config={baseConfig}
        onSaveConfig={onSaveConfig}
      />,
    );
    fireEvent.click(screen.getByTestId("section-row-global_macro-checkbox"));
    fireEvent.click(screen.getByTestId("mb-save-settings"));
    await waitFor(() => expect(onSaveConfig).toHaveBeenCalled());
    const sent = onSaveConfig.mock.calls[0][0] as MbConfig;
    expect(sent.enabled_section_ids).toContain("global_macro");
  });

  it("Add custom section appends with crypto.randomUUID()", async () => {
    const onSaveConfig = vi
      .fn()
      .mockImplementation(async (cfg: MbConfig) => cfg);
    render(
      <MBSettingsView
        config={baseConfig}
        onSaveConfig={onSaveConfig}
      />,
    );
    fireEvent.click(screen.getByTestId("mb-add-custom-section"));
    expect(
      screen.getByTestId("custom-section-row-uuid-fixed-1"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mb-save-settings"));
    await waitFor(() => expect(onSaveConfig).toHaveBeenCalled());
    const sent = onSaveConfig.mock.calls[0][0] as MbConfig;
    expect(sent.custom_sections).toHaveLength(1);
    expect(sent.custom_sections[0].id).toBe("uuid-fixed-1");
  });

  it("Save calls onSaveConfig and shows success toast", async () => {
    const onSaveConfig = vi
      .fn()
      .mockImplementation(async (cfg: MbConfig) => cfg);
    render(
      <MBSettingsView
        config={baseConfig}
        onSaveConfig={onSaveConfig}
      />,
    );
    fireEvent.click(screen.getByTestId("mb-save-settings"));
    await waitFor(() =>
      expect(screen.getByTestId("mb-toast-success")).toBeInTheDocument(),
    );
  });
});
