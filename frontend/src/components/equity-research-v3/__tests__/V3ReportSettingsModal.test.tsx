import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import * as api from "../../../api/equity-research-v3";
import {
  V3ReportSettingsModal,
  type V3SettingsValue,
} from "../V3ReportSettingsModal";

vi.mock("../../../api/equity-research-v3", async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    listV3Templates: vi.fn(),
    deleteV3Template: vi.fn(),
  };
});

const DEFAULT_VALUE: V3SettingsValue = {
  length: "normal",
  language: "en",
  reasoningEffort: "medium",
  templateId: "initiation_default",
  templateName: "Stock Initiation",
};

const TEMPLATES: api.V3TemplateSummary[] = [
  {
    id: "initiation_default",
    name: "Stock Initiation",
    is_builtin: true,
    created_at: "2026-05-27T00:00:00Z",
    updated_at: "2026-05-27T00:00:00Z",
  },
  {
    id: "user-template-abc",
    name: "My custom template",
    is_builtin: false,
    created_at: "2026-05-27T01:00:00Z",
    updated_at: "2026-05-27T01:00:00Z",
  },
];

beforeEach(() => {
  vi.mocked(api.listV3Templates).mockResolvedValue(TEMPLATES);
  vi.mocked(api.deleteV3Template).mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("V3ReportSettingsModal", () => {
  test("renders nothing when closed", () => {
    render(
      <V3ReportSettingsModal
        open={false}
        value={DEFAULT_VALUE}
        onClose={() => undefined}
        onSave={() => undefined}
        onUploadClick={() => undefined}
      />,
    );
    expect(screen.queryByTestId("er-v3-settings-modal")).toBeNull();
  });

  test("stages selection locally and commits on Save", async () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={onClose}
        onSave={onSave}
        onUploadClick={() => undefined}
      />,
    );
    await waitFor(() => expect(api.listV3Templates).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("radio", { name: "Concise" }));
    fireEvent.click(screen.getByTestId("er-v3-settings-save"));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0]).toEqual({
      length: "concise",
      language: "en",
      reasoningEffort: "medium",
      templateId: "initiation_default",
      templateName: "Stock Initiation",
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Cancel closes without firing onSave (staged edits discarded)", async () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={onClose}
        onSave={onSave}
        onUploadClick={() => undefined}
      />,
    );
    await waitFor(() => expect(api.listV3Templates).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("radio", { name: "Elaborative" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("renders the reasoning-effort segmented control and emits the chosen effort on Save", async () => {
    const onSave = vi.fn();
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={() => undefined}
        onSave={onSave}
        onUploadClick={() => undefined}
      />,
    );
    await waitFor(() => expect(api.listV3Templates).toHaveBeenCalled());

    expect(screen.getByTestId("er-v3-reasoning-effort")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Medium" })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    fireEvent.click(screen.getByRole("radio", { name: "High" }));
    fireEvent.click(screen.getByTestId("er-v3-settings-save"));
    expect(onSave.mock.calls[0][0].reasoningEffort).toBe("high");
  });

  test("template picker lists rows from the API and switches selection on click", async () => {
    const onSave = vi.fn();
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={() => undefined}
        onSave={onSave}
        onUploadClick={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("Stock Initiation")).toBeInTheDocument();
    });
    expect(screen.getByText("My custom template")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("er-v3-template-option-user-template-abc"));
    fireEvent.click(screen.getByTestId("er-v3-settings-save"));
    expect(onSave.mock.calls[0][0].templateId).toBe("user-template-abc");
    expect(onSave.mock.calls[0][0].templateName).toBe("My custom template");
  });

  test("clicking Upload fires onUploadClick", async () => {
    const onUploadClick = vi.fn();
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={() => undefined}
        onSave={() => undefined}
        onUploadClick={onUploadClick}
      />,
    );
    await waitFor(() => expect(api.listV3Templates).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("er-v3-template-upload-trigger"));
    expect(onUploadClick).toHaveBeenCalledTimes(1);
  });

  test("deleting a user template removes the row and calls the API", async () => {
    render(
      <V3ReportSettingsModal
        open
        value={DEFAULT_VALUE}
        onClose={() => undefined}
        onSave={() => undefined}
        onUploadClick={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText("My custom template")).toBeInTheDocument();
    });
    fireEvent.click(
      screen.getByLabelText("Delete template My custom template"),
    );
    await waitFor(() => {
      expect(api.deleteV3Template).toHaveBeenCalledWith("user-template-abc");
      expect(screen.queryByText("My custom template")).toBeNull();
    });
  });
});
