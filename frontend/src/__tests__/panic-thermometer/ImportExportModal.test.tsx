import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ImportExportModal } from "../../components/panic-thermometer/ImportExportModal";

describe("ImportExportModal", () => {
  it("parses pasted JSON and calls onImport", () => {
    const onImport = vi.fn();
    const onClose = vi.fn();
    render(
      <ImportExportModal
        open={true}
        onClose={onClose}
        onImport={onImport}
        exportPayload={{ version: 1 }}
      />,
    );
    fireEvent.change(screen.getByTestId("import-text"), {
      target: { value: '{"version":1,"panel_config":[]}' },
    });
    fireEvent.click(screen.getByTestId("import-submit"));
    expect(onImport).toHaveBeenCalledWith({ version: 1, panel_config: [] });
    expect(onClose).toHaveBeenCalled();
  });

  it("shows parse error for invalid JSON", () => {
    render(
      <ImportExportModal
        open={true}
        onClose={() => {}}
        onImport={() => {}}
        exportPayload={null}
      />,
    );
    fireEvent.change(screen.getByTestId("import-text"), {
      target: { value: "not json" },
    });
    fireEvent.click(screen.getByTestId("import-submit"));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
