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
      name: "Stock Initiation",
      shape_description: "Full initiation.",
      ticker_anchored: true,
      sections: [
        { id: "overview", title: "Overview", intent: "x", methodology_hints: [] },
      ],
    },
  },
  {
    report_type: "sector_research" as const,
    template_spec: {
      template_id: "sector_research_default",
      name: "Sector Research",
      shape_description: "Sector primer.",
      ticker_anchored: false,
      sections: [
        { id: "primer", title: "Primer", intent: "x", methodology_hints: [] },
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Stock Initiation")).toBeInTheDocument(),
    );
    expect(screen.getByText("Sector Research")).toBeInTheDocument();
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Sector Research"));
    fireEvent.click(
      screen.getByTestId("er-v2-3-settings-builtin-sector_research"),
    );
    expect(onSelectionChange).toHaveBeenCalledWith({
      templateId: null,
      reportType: "sector_research",
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Stock Initiation"));
    fireEvent.click(screen.getByTestId("er-v2-3-settings-length-elaborative"));
    expect(onLengthChange).toHaveBeenCalledWith("elaborative");
  });

  test("renders the reasoning pill with Off / Medium / High and the current value checked", async () => {
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        reasoningEffort="medium"
        onReasoningEffortChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Stock Initiation"));
    expect(screen.getByTestId("er-v2-3-settings-reasoning-off")).toBeInTheDocument();
    expect(
      screen.getByTestId("er-v2-3-settings-reasoning-medium"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("er-v2-3-settings-reasoning-high")).toBeInTheDocument();
    expect(
      screen
        .getByTestId("er-v2-3-settings-reasoning-medium")
        .getAttribute("aria-checked"),
    ).toBe("true");
  });

  test("clicking a reasoning option fires onReasoningEffortChange", async () => {
    const onReasoningEffortChange = vi.fn();
    render(
      <V23ReportSettingsModal
        open
        selection={defaultSelection()}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        reasoningEffort="off"
        onReasoningEffortChange={onReasoningEffortChange}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Stock Initiation"));
    fireEvent.click(screen.getByTestId("er-v2-3-settings-reasoning-high"));
    expect(onReasoningEffortChange).toHaveBeenCalledWith("high");
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
        onUploadClick={onUploadClick}
        onClose={onClose}
      />,
    );
    await waitFor(() => screen.getByText("Stock Initiation"));
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
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
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
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
        selection={{ templateId: null, reportType: "sector_research" }}
        length="normal"
        onSelectionChange={vi.fn()}
        onLengthChange={vi.fn()}
        reasoningEffort="off"
        onReasoningEffortChange={vi.fn()}
        onUploadClick={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => screen.getByText("Sector Research"));
    const row = screen.getByTestId("er-v2-3-settings-builtin-sector_research");
    expect(row).toHaveAttribute("aria-checked", "true");
    const other = screen.getByTestId("er-v2-3-settings-builtin-initiation");
    expect(other).toHaveAttribute("aria-checked", "false");
  });
});
