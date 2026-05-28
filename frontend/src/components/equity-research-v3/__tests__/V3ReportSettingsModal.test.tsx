import { describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  V3ReportSettingsModal,
  type V3SettingsValue,
} from "../V3ReportSettingsModal";

const DEFAULT_VALUE: V3SettingsValue = {
  reportType: "initiation",
  length: "normal",
  language: "en",
};

describe("V3ReportSettingsModal", () => {
  test("renders nothing when closed", () => {
    render(
      <V3ReportSettingsModal
        open={false}
        value={DEFAULT_VALUE}
        onClose={() => undefined}
        onSave={() => undefined}
      />,
    );
    expect(screen.queryByTestId("er-v3-settings-modal")).toBeNull();
  });

  test("stages selection locally and commits on Save", () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={onClose}
        onSave={onSave}
      />,
    );

    // Switch report type and length, then save.
    fireEvent.click(screen.getByRole("radio", { name: "Stock Update" }));
    fireEvent.click(screen.getByRole("radio", { name: "Concise" }));
    fireEvent.click(screen.getByTestId("er-v3-settings-save"));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0]).toEqual({
      reportType: "update",
      length: "concise",
      language: "en",
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Cancel closes without firing onSave (staged edits discarded)", () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={onClose}
        onSave={onSave}
      />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "Elaborative" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("renders Coming Soon placeholders for reasoning effort and template", () => {
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={() => undefined}
        onSave={() => undefined}
      />,
    );
    expect(
      screen.getByTestId("er-v3-settings-coming-soon-reasoning-effort"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("er-v3-settings-coming-soon-template"),
    ).toBeInTheDocument();
  });
});
