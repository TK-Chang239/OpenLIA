import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DeleteReportDialog } from "../DeleteReportDialog";

describe("DeleteReportDialog", () => {
  it("does not render content when closed", () => {
    render(
      <DeleteReportDialog
        open={false}
        reportTitle="AAPL — Initiation"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("delete-report-dialog")).toBeNull();
  });

  it("renders the title and confirm/cancel actions", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <DeleteReportDialog
        open={true}
        reportTitle="AAPL — Initiation"
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByTestId("delete-report-dialog")).toBeInTheDocument();
    expect(screen.getByText(/"AAPL — Initiation"/)).toBeInTheDocument();
    expect(screen.getByText(/no longer available/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
