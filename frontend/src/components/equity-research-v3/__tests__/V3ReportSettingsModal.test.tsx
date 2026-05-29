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
    listV3Instructions: vi.fn(),
    deleteV3Instructions: vi.fn(),
  };
});

const DEFAULT_VALUE: V3SettingsValue = {
  length: "normal",
  language: "en",
  reasoningEffort: "medium",
  templateId: "initiation_default",
  templateName: "Stock Initiation",
  instructionsId: null,
  instructionsName: null,
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

const INSTRUCTIONS: api.V3InstructionsSummary[] = [
  {
    id: "instr-xyz",
    name: "Winner framework",
    is_builtin: false,
    created_at: "2026-05-28T00:00:00Z",
    updated_at: "2026-05-28T00:00:00Z",
  },
];

interface RenderOverrides {
  value?: V3SettingsValue;
  onSave?: () => void;
  onClose?: () => void;
  onUploadClick?: () => void;
  onUploadInstructionsClick?: () => void;
}

function renderModal(overrides: RenderOverrides = {}) {
  const props = {
    onClose: () => undefined,
    onSave: () => undefined,
    onUploadClick: () => undefined,
    onUploadInstructionsClick: () => undefined,
    ...overrides,
  };
  return render(
    <V3ReportSettingsModal open value={overrides.value ?? DEFAULT_VALUE} {...props} />,
  );
}

beforeEach(() => {
  vi.mocked(api.listV3Templates).mockResolvedValue(TEMPLATES);
  vi.mocked(api.deleteV3Template).mockResolvedValue(undefined);
  vi.mocked(api.listV3Instructions).mockResolvedValue(INSTRUCTIONS);
  vi.mocked(api.deleteV3Instructions).mockResolvedValue(undefined);
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
        onUploadInstructionsClick={() => undefined}
      />,
    );
    expect(screen.queryByTestId("er-v3-settings-modal")).toBeNull();
  });

  test("stages selection locally and commits on Save", async () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    renderModal({ onSave, onClose });
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
      instructionsId: null,
      instructionsName: null,
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Cancel closes without firing onSave (staged edits discarded)", async () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    renderModal({ onSave, onClose });
    await waitFor(() => expect(api.listV3Templates).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("radio", { name: "Elaborative" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("renders the reasoning-effort segmented control and emits the chosen effort on Save", async () => {
    const onSave = vi.fn();
    renderModal({ onSave });
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
    renderModal({ onSave });
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
    renderModal({ onUploadClick });
    await waitFor(() => expect(api.listV3Templates).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("er-v3-template-upload-trigger"));
    expect(onUploadClick).toHaveBeenCalledTimes(1);
  });

  test("deleting a user template removes the row and calls the API", async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText("My custom template")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText("Delete template My custom template"));
    await waitFor(() => {
      expect(api.deleteV3Template).toHaveBeenCalledWith("user-template-abc");
      expect(screen.queryByText("My custom template")).toBeNull();
    });
  });

  // --- instructions + freeform ---------------------------------------------

  test("instruction profiles list from the API and selection commits on Save", async () => {
    const onSave = vi.fn();
    renderModal({ onSave });
    await waitFor(() => expect(api.listV3Instructions).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("er-v3-instructions-option-instr-xyz"));
    fireEvent.click(screen.getByTestId("er-v3-settings-save"));
    expect(onSave.mock.calls[0][0].instructionsId).toBe("instr-xyz");
    expect(onSave.mock.calls[0][0].instructionsName).toBe("Winner framework");
  });

  test("picking No template + an instruction profile commits freeform", async () => {
    const onSave = vi.fn();
    renderModal({ onSave });
    await waitFor(() => expect(api.listV3Instructions).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("er-v3-template-option-freeform"));
    fireEvent.click(screen.getByTestId("er-v3-instructions-option-instr-xyz"));
    fireEvent.click(screen.getByTestId("er-v3-settings-save"));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0].templateId).toBe("freeform");
    expect(onSave.mock.calls[0][0].instructionsId).toBe("instr-xyz");
  });

  test("No template without instructions blocks Save and shows a hint", async () => {
    const onSave = vi.fn();
    renderModal({ onSave });
    await waitFor(() => expect(api.listV3Instructions).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("er-v3-template-option-freeform"));
    expect(
      screen.getByTestId("er-v3-freeform-needs-instructions"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("er-v3-settings-save"));
    expect(onSave).not.toHaveBeenCalled();
  });

  test("clicking Upload (instructions) fires onUploadInstructionsClick", async () => {
    const onUploadInstructionsClick = vi.fn();
    renderModal({ onUploadInstructionsClick });
    await waitFor(() => expect(api.listV3Instructions).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("er-v3-instructions-upload-trigger"));
    expect(onUploadInstructionsClick).toHaveBeenCalledTimes(1);
  });
});
