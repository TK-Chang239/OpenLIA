import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SignalAlert } from "../SignalAlert";

describe("SignalAlert", () => {
  it("renders ticker and z-score", () => {
    render(
      <SignalAlert
        spike={{
          ticker: "AAPL",
          detected_at: new Date().toISOString(),
          buzz: 50,
          baseline_mean: 10,
          baseline_stddev: 2.5,
          z_score: 4.0,
        }}
      />,
    );
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText(/z\s*=\s*4\.00/)).toBeInTheDocument();
  });

  it("invokes onPick when clicked", () => {
    const onPick = vi.fn();
    render(
      <SignalAlert
        onPick={onPick}
        spike={{
          ticker: "MSFT",
          detected_at: new Date().toISOString(),
          buzz: 80,
          baseline_mean: 12,
          baseline_stddev: 3,
          z_score: 5,
        }}
      />,
    );
    fireEvent.click(screen.getByTestId("signal-MSFT"));
    expect(onPick).toHaveBeenCalledWith("MSFT");
  });
});
