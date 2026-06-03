import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MbCabinetView } from "../MbCabinetView";

const noop = vi.fn().mockResolvedValue(undefined);

const STAMP = "2026-06-01T00:00:00Z";

function renderCabinet() {
  render(
    <MbCabinetView
      templates={[
        {
          id: "t1",
          name: "Builtin Tpl",
          is_builtin: true,
          created_at: STAMP,
          updated_at: STAMP,
        },
        {
          id: "t2",
          name: "My Tpl",
          is_builtin: false,
          created_at: STAMP,
          updated_at: STAMP,
        },
      ]}
      instructions={[]}
      onBack={vi.fn()}
      onUploadTemplateMarkdown={noop}
      onUploadTemplateFile={noop}
      onUploadInstructions={noop}
      onRemoveTemplate={noop}
      onRemoveInstructions={noop}
    />,
  );
}

describe("MbCabinetView", () => {
  it("renders template rows with a built-in badge and an upload trigger", () => {
    renderCabinet();
    expect(screen.getByText("Builtin Tpl")).toBeInTheDocument();
    expect(screen.getByText("My Tpl")).toBeInTheDocument();
    expect(
      screen.getByTestId("mb-cabinet-upload-template"),
    ).toBeInTheDocument();
  });

  it("opens the delete confirm for a user template", () => {
    renderCabinet();
    fireEvent.click(screen.getByTestId("mb-cabinet-delete-template-t2"));
    expect(screen.getByText("My Tpl")).toBeInTheDocument();
  });
});
