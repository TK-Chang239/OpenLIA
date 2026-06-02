import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EuRefreshButton } from "../EuRefreshButton";

describe("EuRefreshButton", () => {
  it("invokes onRefresh and shows the synced count", async () => {
    const onRefresh = vi.fn().mockResolvedValue(6);
    render(<EuRefreshButton onRefresh={onRefresh} />);

    fireEvent.click(
      screen.getByRole("button", { name: /refresh earnings dates/i }),
    );

    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByText(/updated.*6 tickers/i),
    ).toBeInTheDocument();
  });

  it("does not fire onRefresh when disabled", () => {
    const onRefresh = vi.fn().mockResolvedValue(0);
    render(<EuRefreshButton onRefresh={onRefresh} disabled />);

    fireEvent.click(
      screen.getByRole("button", { name: /refresh earnings dates/i }),
    );

    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("shows a failure message when onRefresh rejects", async () => {
    const onRefresh = vi.fn().mockRejectedValue(new Error("boom"));
    render(<EuRefreshButton onRefresh={onRefresh} />);

    fireEvent.click(
      screen.getByRole("button", { name: /refresh earnings dates/i }),
    );

    expect(await screen.findByText(/refresh failed/i)).toBeInTheDocument();
  });
});
