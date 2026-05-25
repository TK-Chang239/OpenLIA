import { beforeEach, describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import * as api from "../../api/report-templates";
import {
  V23ReportSettingsModal,
  type V23SettingsSelection,
} from "./V23ReportSettingsModal";

vi.mock("../../api/report-templates");

const BUILTINS = [
  {
    report_type: "initiation" as const,
    template_spec: {
      template_id: "initiation_default",
      name: "Initiation (default)",
      shape_description: "Full initiation.",
      ticker_anchored: true,
      sections: [
        { id: "overview", title: "Overview", intent: "x", methodology_hints: [] },
      ],
    },
  },
  {
    report_type: "morning_brief" as const,
    template_spec: {
      template_id: "morning_brief_default",
      name: "Morning Brief (default)",
      shape_description: "Pre-market brief.",
      ticker_anchored: true,
      sections: [
        { id: "overnight", title: "Overnight", intent: "x", methodology_hints: [] },
      ],
    },
  },
];

const USER_TEMPLATE = {
  id: "row-uuid-1",
  name: "My Custom Template",
  template_spec: {
    template_id: "custom_aaaa1111",
    name: "My Custom Template",
    shape_description: "User-defined.",
    ticker_anchored: true,
    sections: [
      { id: "s1", title: "S1", intent: "x", methodology_hints: [] },
      { id: "s2", title: "S2", intent: "y", methodology_hints: [] },
    ],
  },
  source_markdown: null,
  created_at: "2026-05-25T00:00:00Z",
  updated_at: "2026-05-25T00:00:00Z",
};

function defaultSelection(): V23SettingsSelection {
  return { templateId: null, reportType: "initiation" };
}

describe("V23ReportSettingsModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchV23Builtins).mockResolvedValue(BUILTINS);
    vi.mocked(api.listReportTemplates).mockResolvedValue([USER_TEMPLATE]);
  });

  test("renders nothing when closed", () => {
    const { container } = render(
      <V23ReportSettingsModal
        open={false}
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  test("renders builtins and user templates as flat siblings", async () => {
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Initiation (default)")).toBeInTheDocument(),
    );
    expect(screen.getByText("Morning Brief (default)")).toBeInTheDocument();
    expect(screen.getByText("My Custom Template")).toBeInTheDocument();
  });

  test("clicking a builtin emits {templateId:null, reportType:<built-in>}", async () => {
    const onSelectionChange = vi.fn();
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={onSelectionChange}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Morning Brief (default)"));
    fireEvent.click(
      screen.getByTestId("er-v2-3-settings-builtin-morning_brief"),
    );
    expect(onSelectionChange).toHaveBeenCalledWith({
      templateId: null,
      reportType: "morning_brief",
    });
  });

  test("clicking a user template emits its row id with the default reportType", async () => {
    const onSelectionChange = vi.fn();
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={onSelectionChange}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("My Custom Template"));
    fireEvent.click(
      screen.getByTestId("er-v2-3-settings-user-template-row-uuid-1"),
    );
    expect(onSelectionChange).toHaveBeenCalledWith({
      templateId: "row-uuid-1",
      reportType: "initiation",
    });
  });

  test("clicking a length option fires onLengthChange", async () => {
    const onLengthChange = vi.fn();
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={onLengthChange}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Initiation (default)"));
    fireEvent.click(screen.getByTestId("er-v2-3-settings-length-elaborative"));
    expect(onLengthChange).toHaveBeenCalledWith("elaborative");
  });

  test("clicking upload fires onUploadClick without closing", async () => {
    const onUploadClick = vi.fn();
    const onClose = vi.fn();
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        onUploadClick={onUploadClick}
        onClose={onClose}
      />,
    );
    await waitFor(() => screen.getByText("Initiation (default)"));
    fireEvent.click(screen.getByTestId("er-v2-3-settings-upload"));
    expect(onUploadClick).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  test("refreshKey change retriggers the templates fetch", async () => {
    const { rerender } = render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
        refreshKey={0}
      />,
    );
    await waitFor(() => screen.getByText("My Custom Template"));
    expect(api.listReportTemplates).toHaveBeenCalledTimes(1);
    rerender(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
        refreshKey={1}
      />,
    );
    await waitFor(() =>
      expect(api.listReportTemplates).toHaveBeenCalledTimes(2),
    );
  });

  test("surface fetch errors inline without crashing the modal", async () => {
    vi.mocked(api.fetchV23Builtins).mockRejectedValue(
      new Error("network down"),
    );
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("er-v2-3-settings-load-error"),
      ).toHaveTextContent("network down"),
    );
  });

  test("active selection renders the radio in the checked state", async () => {
    render(
      <V23ReportSettingsModal
        open
        selection={{ templateId: null, reportType: "morning_brief" }}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Morning Brief (default)"));
    const row = screen.getByTestId("er-v2-3-settings-builtin-morning_brief");
    expect(row).toHaveAttribute("aria-checked", "true");
    const other = screen.getByTestId("er-v2-3-settings-builtin-initiation");
    expect(other).toHaveAttribute("aria-checked", "false");
  });
});
