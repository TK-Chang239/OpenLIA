import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportSettingsModal } from "../ReportSettingsModal";

const baseConfig = {
  report_length: "normal" as const,
  enabled_section_ids: ["quick_take", "key_financials"],
  custom_sections: [],
};

describe("ReportSettingsModal", () => {
  it("renders all 8 section toggles", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    expect(screen.getAllByRole("checkbox").length).toBeGreaterThanOrEqual(8);
  });

  it("toggles include/exclude a section", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />,
    );
    const box = screen.getByLabelText(/Quick Take/i) as HTMLInputElement;
    expect(box.checked).toBe(true);
    fireEvent.click(box);
    expect(box.checked).toBe(false);
  });

  it("saves with new selections and length", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByLabelText(/elaborative/i));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const payload = onSave.mock.calls[0][0];
    expect(payload.report_length).toBe("elaborative");
  });

  it("adds a custom section", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={onSave}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /\+ custom section/i }));
    const rows = screen.getAllByPlaceholderText(/section title/i);
    fireEvent.change(rows[rows.length - 1], {
      target: { value: "Model update" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0].custom_sections[0].title).toBe(
      "Model update",
    );
  });
});
