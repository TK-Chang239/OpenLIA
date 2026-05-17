import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RevisionInProgressChip } from "../RevisionInProgressChip";

describe("RevisionInProgressChip", () => {
  it("renders a revision-in-progress status with a Cancel button", () => {
    render(<RevisionInProgressChip newReportId="r_xyz" />);
    expect(screen.getByText(/revising/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel revision/i })).toBeInTheDocument();
  });

  it("calls DELETE /reports/{newReportId} when Cancel clicked", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({ ok: true } as any);
    window.confirm = vi.fn(() => true);
    render(<RevisionInProgressChip newReportId="r_xyz" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel revision/i }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith("/reports/r_xyz", { method: "DELETE" }));
  });
});
