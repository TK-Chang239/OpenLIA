import { describe, expect, test, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { V23TemplateUploadModal } from "./V23TemplateUploadModal";
import * as api from "../../api/report-templates";

vi.mock("../../api/report-templates");

describe("V23TemplateUploadModal", () => {
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
});
