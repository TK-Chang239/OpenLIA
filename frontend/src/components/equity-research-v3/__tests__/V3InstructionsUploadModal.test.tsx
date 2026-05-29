import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import * as v3api from "../../../api/equity-research-v3";
import { V3InstructionsUploadModal } from "../V3InstructionsUploadModal";

vi.mock("../../../api/equity-research-v3", async (importOriginal) => {
  const actual = await importOriginal<typeof v3api>();
  return {
    ...actual,
    uploadV3Instructions: vi.fn(),
  };
});

const CREATED: v3api.V3InstructionsSummary = {
  id: "instr-1",
  name: "framework",
  is_builtin: false,
  created_at: "2026-05-29T00:00:00Z",
  updated_at: "2026-05-29T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(v3api.uploadV3Instructions).mockResolvedValue(CREATED);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("V3InstructionsUploadModal", () => {
  test("renders nothing when closed", () => {
    render(
      <V3InstructionsUploadModal
        open={false}
        onClose={() => undefined}
        onSaved={() => undefined}
      />,
    );
    expect(screen.queryByTestId("v3-instructions-upload-modal")).toBeNull();
  });

  test("picking a supported file auto-fills the name and uploads the raw file", async () => {
    const onSaved = vi.fn();
    const onClose = vi.fn();
    render(
      <V3InstructionsUploadModal open onClose={onClose} onSaved={onSaved} />,
    );

    const file = new File(["methodology text"], "framework.md", {
      type: "text/markdown",
    });
    const input = screen.getByTestId(
      "v3-instructions-upload-file-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      const nameField = screen.getByTestId(
        "v3-instructions-upload-name",
      ) as HTMLInputElement;
      expect(nameField.value).toBe("framework");
    });

    fireEvent.click(screen.getByTestId("v3-instructions-upload-save"));

    await waitFor(() => {
      expect(v3api.uploadV3Instructions).toHaveBeenCalledTimes(1);
      const [name, uploaded] = vi.mocked(v3api.uploadV3Instructions).mock.calls[0];
      expect(name).toBe("framework");
      expect((uploaded as File).name).toBe("framework.md");
      expect(onSaved).toHaveBeenCalledWith(CREATED);
      expect(onClose).toHaveBeenCalled();
    });
  });

  test("rejects unsupported file types with an inline error", async () => {
    render(
      <V3InstructionsUploadModal
        open
        onClose={() => undefined}
        onSaved={() => undefined}
      />,
    );

    const file = new File(["{}"], "spec.json", { type: "application/json" });
    const input = screen.getByTestId(
      "v3-instructions-upload-file-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByTestId("v3-instructions-upload-error"),
      ).toHaveTextContent("Unsupported file type");
    });
    expect(v3api.uploadV3Instructions).not.toHaveBeenCalled();
  });
});
