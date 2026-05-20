import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CustomTemplatesSection } from "../CustomTemplatesSection";
import * as api from "../../../../api/report-templates";

const SAMPLE_PARSED: api.ParsedTemplate = {
  global_preface: "Top-level preamble.",
  document_frontmatter: {},
  sections: [
    {
      id: "intro",
      title: "Intro",
      brief: "introductory prose",
      frontmatter: {},
    },
    {
      id: "analysis",
      title: "Analysis",
      brief: "analysis prose",
      frontmatter: { voice: "third_person_only" },
    },
  ],
  template_spec: {
    name: "Sample",
    global_preface: "Top-level preamble.",
    body_sections: [
      { id: "intro", title: "Intro", brief: "introductory prose" },
      { id: "analysis", title: "Analysis", brief: "analysis prose" },
    ],
    synthesis_sections: [],
  },
};

describe("CustomTemplatesSection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lists templates returned by the API", async () => {
    vi.spyOn(api, "listReportTemplates").mockResolvedValue([
      {
        id: "t1",
        name: "Stock Initiation v3",
        template_spec: {
          body_sections: [{}, {}, {}],
          synthesis_sections: [{}],
        },
        source_markdown: null,
        created_at: "2026-05-20T00:00:00Z",
        updated_at: "2026-05-20T00:00:00Z",
      },
    ]);

    render(<CustomTemplatesSection />);

    await waitFor(() =>
      expect(screen.getByText("Stock Initiation v3")).toBeInTheDocument(),
    );
    expect(screen.getByText(/4 sections/)).toBeInTheDocument();
  });

  it("ingests, parses, and saves an uploaded markdown file", async () => {
    vi.spyOn(api, "listReportTemplates").mockResolvedValue([]);
    const ingestSpy = vi
      .spyOn(api, "ingestTemplateDocument")
      .mockResolvedValue({ markdown: "# Intro\nbody\n" });
    const parseSpy = vi
      .spyOn(api, "parseTemplateMarkdown")
      .mockResolvedValue(SAMPLE_PARSED);
    const createSpy = vi
      .spyOn(api, "createReportTemplate")
      .mockResolvedValue({
        id: "new",
        name: "Sample",
        template_spec: SAMPLE_PARSED.template_spec,
        source_markdown: "# Intro\nbody\n",
        created_at: "2026-05-20T00:00:00Z",
        updated_at: "2026-05-20T00:00:00Z",
      });

    render(<CustomTemplatesSection />);

    await waitFor(() => expect(api.listReportTemplates).toHaveBeenCalled());

    const file = new File(["# Intro\nbody\n"], "Sample.md", {
      type: "text/markdown",
    });
    const input = screen.getByTestId(
      "template-upload-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(ingestSpy).toHaveBeenCalled());
    await waitFor(() => expect(parseSpy).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByTestId("parsed-section-intro")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("parsed-section-analysis")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("template-save-button"));

    await waitFor(() => expect(createSpy).toHaveBeenCalled());
    const callArg = createSpy.mock.calls[0][0];
    expect(callArg.name).toBe("Sample");
    expect(callArg.templateSpec).toEqual(SAMPLE_PARSED.template_spec);
  });

  it("surfaces an ingest error without leaving the form busy", async () => {
    vi.spyOn(api, "listReportTemplates").mockResolvedValue([]);
    vi.spyOn(api, "ingestTemplateDocument").mockRejectedValue(
      new Error("unsupported mime type"),
    );

    render(<CustomTemplatesSection />);

    const file = new File(["binary"], "logo.png", { type: "image/png" });
    fireEvent.change(screen.getByTestId("template-upload-input"), {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /unsupported mime type/i,
      ),
    );
    const upload = screen.getByTestId(
      "template-upload-input",
    ) as HTMLInputElement;
    expect(upload).not.toBeDisabled();
  });
});
