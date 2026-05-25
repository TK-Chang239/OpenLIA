import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { V23TemplateUploadModal } from "./V23TemplateUploadModal";
import * as api from "../../api/report-templates";

vi.mock("../../api/report-templates");

describe("V23TemplateUploadModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  test("renders the markdown textarea and a parse button when open", () => {
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    expect(screen.getByLabelText(/markdown/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /parse/i })).toBeInTheDocument();
  });

  test("renders nothing when closed", () => {
    const { container } = render(
      <V23TemplateUploadModal
        open={false}
        onSaved={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  test("calls parseMarkdownV23 and renders parsed sections", async () => {
    vi.mocked(api.parseMarkdownV23).mockResolvedValue({
      template_spec: {
        template_id: "x_abcd1234",
        name: "X",
        shape_description: "s",
        ticker_anchored: true,
        sections: [
          { id: "alpha", title: "Alpha", intent: "A.", methodology_hints: [] },
        ],
      },
      validation_errors: [],
    });
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText(/markdown/i), {
      target: { value: "# Alpha\nbody" },
    });
    fireEvent.click(screen.getByRole("button", { name: /parse/i }));
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
    });
  });

  test("save persists the parsed spec and calls onSaved with the new id", async () => {
    vi.mocked(api.parseMarkdownV23).mockResolvedValue({
      template_spec: {
        template_id: "x_abcd1234",
        name: "X",
        shape_description: "s",
        ticker_anchored: true,
        sections: [
          { id: "alpha", title: "Alpha", intent: "A.", methodology_hints: [] },
        ],
      },
      validation_errors: [],
    });
    vi.mocked(api.saveReportTemplate).mockResolvedValue({
      id: "row-uuid",
      name: "X",
      template_spec: {
        template_id: "x_abcd1234",
        name: "X",
        shape_description: "s",
        ticker_anchored: true,
        sections: [
          { id: "alpha", title: "Alpha", intent: "A.", methodology_hints: [] },
        ],
      },
      source_markdown: null,
      created_at: "2026-05-25",
      updated_at: "2026-05-25",
    });
    const onSaved = vi.fn();
    render(<V23TemplateUploadModal open onSaved={onSaved} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/markdown/i), {
      target: { value: "# Alpha\nbody" },
    });
    fireEvent.click(screen.getByRole("button", { name: /parse/i }));
    await waitFor(() => screen.getByText("Alpha"));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith("row-uuid"));
  });

  test("renders validation_errors when parse returns them", async () => {
    vi.mocked(api.parseMarkdownV23).mockResolvedValue({
      template_spec: {} as never,
      validation_errors: ["sections: at least one section required"],
    });
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText(/markdown/i), {
      target: { value: "no headings" },
    });
    fireEvent.click(screen.getByRole("button", { name: /parse/i }));
    await waitFor(() =>
      expect(
        screen.getByText(/at least one section required/i),
      ).toBeInTheDocument(),
    );
  });

  test("uploading a .md file reads it and parses through the markdown path", async () => {
    vi.mocked(api.parseMarkdownV23).mockResolvedValue({
      template_spec: {
        template_id: "init_abcd1234",
        name: "InitNote",
        shape_description: "s",
        ticker_anchored: true,
        sections: [
          { id: "beta", title: "Beta", intent: "B.", methodology_hints: [] },
        ],
      },
      validation_errors: [],
    });
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    const fileInput = screen.getByTestId(
      "er-v2-3-template-upload-file",
    ) as HTMLInputElement;
    const file = new File(["# Beta\nbody"], "InitNote.md", {
      type: "text/markdown",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => {
      expect(screen.getByText("Beta")).toBeInTheDocument();
    });
    expect(api.parseMarkdownV23).toHaveBeenCalledWith(
      "# Beta\nbody",
      "InitNote",
    );
  });

  test("uploading a .docx routes through ingest then parse", async () => {
    vi.mocked(api.ingestTemplateDocument).mockResolvedValue({
      markdown: "# Quarter Highlights\nbody",
    });
    vi.mocked(api.parseMarkdownV23).mockResolvedValue({
      template_spec: {
        template_id: "er_abcd1234",
        name: "Earnings",
        shape_description: "s",
        ticker_anchored: true,
        sections: [
          {
            id: "quarter_highlights",
            title: "Quarter Highlights",
            intent: "Q.",
            methodology_hints: [],
          },
        ],
      },
      validation_errors: [],
    });
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    const fileInput = screen.getByTestId(
      "er-v2-3-template-upload-file",
    ) as HTMLInputElement;
    const file = new File(["binary-docx-bytes"], "Earnings.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => {
      expect(screen.getByText("Quarter Highlights")).toBeInTheDocument();
    });
    expect(api.ingestTemplateDocument).toHaveBeenCalledWith(file);
    expect(api.parseMarkdownV23).toHaveBeenCalledWith(
      "# Quarter Highlights\nbody",
      "Earnings",
    );
  });

  test("uploading a .json validates through the JSON path", async () => {
    vi.mocked(api.validateV23TemplateJson).mockResolvedValue({
      template_spec: {
        template_id: "u_abcd1234",
        name: "Custom",
        shape_description: "s",
        ticker_anchored: true,
        sections: [
          { id: "alpha", title: "Alpha", intent: "A.", methodology_hints: [] },
        ],
      },
      validation_errors: [],
    });
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    const fileInput = screen.getByTestId(
      "er-v2-3-template-upload-file",
    ) as HTMLInputElement;
    const json = JSON.stringify({
      template_id: "u_abcd1234",
      name: "Custom",
      shape_description: "s",
      ticker_anchored: true,
      sections: [
        { id: "alpha", title: "Alpha", intent: "A.", methodology_hints: [] },
      ],
    });
    const file = new File([json], "custom.json", { type: "application/json" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
    });
    expect(api.validateV23TemplateJson).toHaveBeenCalledWith(
      expect.objectContaining({ template_id: "u_abcd1234" }),
    );
    // Markdown path must NOT be invoked for JSON uploads.
    expect(api.parseMarkdownV23).not.toHaveBeenCalled();
  });

  test("uploading a .json with bad JSON surfaces the syntax error inline", async () => {
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    const fileInput = screen.getByTestId(
      "er-v2-3-template-upload-file",
    ) as HTMLInputElement;
    const file = new File(["{not valid"], "bad.json", {
      type: "application/json",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => {
      expect(screen.getByText(/Invalid JSON in bad\.json/)).toBeInTheDocument();
    });
    expect(api.validateV23TemplateJson).not.toHaveBeenCalled();
  });

  test("unsupported file extension reports a friendly error", async () => {
    render(
      <V23TemplateUploadModal open onSaved={vi.fn()} onClose={vi.fn()} />,
    );
    const fileInput = screen.getByTestId(
      "er-v2-3-template-upload-file",
    ) as HTMLInputElement;
    const file = new File(["hello"], "image.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    await waitFor(() => {
      expect(
        screen.getByText(/Unsupported file type: image\.png/),
      ).toBeInTheDocument();
    });
  });
});
