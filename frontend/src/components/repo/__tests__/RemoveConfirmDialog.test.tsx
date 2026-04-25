import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RemoveConfirmDialog } from "../RemoveConfirmDialog";

describe("RemoveConfirmDialog", () => {
  it("does not render content when closed", () => {
    render(
      <RemoveConfirmDialog open={false} filename="x.pdf" onCancel={vi.fn()} onConfirm={vi.fn()} />,
    );
    expect(screen.queryByTestId("remove-confirm-dialog")).toBeNull();
  });

  it("renders dialog with filename and dispatches confirm/cancel", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <RemoveConfirmDialog
        open={true}
        filename="report.pdf"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByTestId("remove-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByText(/"report.pdf"/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});
