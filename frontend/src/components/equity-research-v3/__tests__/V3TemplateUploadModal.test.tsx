import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import * as v3api from "../../../api/equity-research-v3";
import * as templatesApi from "../../../api/report-templates";
import { V3TemplateUploadModal } from "../V3TemplateUploadModal";

vi.mock("../../../api/equity-research-v3", async (importOriginal) => {
  const actual = await importOriginal<typeof v3api>();
  return {
    ...actual,
    uploadV3Template: vi.fn(),
  };
});

vi.mock("../../../api/report-templates", async (importOriginal) => {
  const actual = await importOriginal<typeof templatesApi>();
  return {
    ...actual,
    ingestTemplateDocument: vi.fn(),
  };
});

const CREATED: v3api.V3TemplateSummary = {
  id: "user-tpl-1",
  name: "Test template",
  is_builtin: false,
  created_at: "2026-05-27T00:00:00Z",
  updated_at: "2026-05-27T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(v3api.uploadV3Template).mockResolvedValue(CREATED);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("V3TemplateUploadModal", () => {
  test("renders nothing when closed", () => {
    render(
      <V3TemplateUploadModal
        open={false}
        onClose={() => undefined}
        onSaved={() => undefined}
      />,
    );
    expect(screen.queryByTestId("v3-template-upload-modal")).toBeNull();
  });

  test("uploading a .md file enables Save and posts the markdown body", async () => {
    const onSaved = vi.fn();
    const onClose = vi.fn();
    render(
      <V3TemplateUploadModal
        open
        onClose={onClose}
        onSaved={onSaved}
      />,
    );

    const md = "# Section A\n\nbody.\n\n# Section B\n\nbody.";
    const file = new File([md], "my-template.md", { type: "text/markdown" });
    const input = screen.getByTestId(
      "v3-template-upload-file-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    // Name auto-fills from filename
    await waitFor(() => {
      const nameField = screen.getByTestId(
        "v3-template-upload-name",
      ) as HTMLInputElement;
      expect(nameField.value).toBe("my-template");
    });
    // Preview shows section count
    expect(
      screen.getByTestId("v3-template-upload-preview"),
    ).toHaveTextContent("Parsed 2 section(s)");

    fireEvent.click(screen.getByTestId("v3-template-upload-save"));

    await waitFor(() => {
      expect(v3api.uploadV3Template).toHaveBeenCalledTimes(1);
      const [arg] = vi.mocked(v3api.uploadV3Template).mock.calls[0];
      expect(arg.name).toBe("my-template");
      expect(arg.markdown).toBe(md);
      expect(arg.source_doc_blob).toBeNull();
      expect(onSaved).toHaveBeenCalledWith(CREATED);
      expect(onClose).toHaveBeenCalled();
    });
  });

  test("rejects unsupported file types with an inline error", async () => {
    render(
      <V3TemplateUploadModal
        open
        onClose={() => undefined}
        onSaved={() => undefined}
      />,
    );

    const file = new File(["{}"], "spec.json", { type: "application/json" });
    const input = screen.getByTestId(
      "v3-template-upload-file-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByTestId("v3-template-upload-error"),
      ).toHaveTextContent("Unsupported file type");
    });
  });

  test("docx upload routes through ingestTemplateDocument (mammoth conversion)", async () => {
    // jsdom's File.arrayBuffer() landing race makes the full save path
    // flaky in tests — the actual end-to-end docx flow is covered by
    // the v2.3 ingest tests + a manual browser smoke. Here we just
    // verify the docx branch wires to the existing ingest helper.
    const md = "# Heading\n\nbody";
    vi.mocked(templatesApi.ingestTemplateDocument).mockResolvedValue({
      markdown: md,
    });
    render(
      <V3TemplateUploadModal
        open
        onClose={() => undefined}
        onSaved={() => undefined}
      />,
    );

    const file = new File(["fake-docx"], "report.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    const input = screen.getByTestId(
      "v3-template-upload-file-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(templatesApi.ingestTemplateDocument).toHaveBeenCalledWith(file);
    });
  });
});
