import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SignalAlert } from "../SignalAlert";

describe("SignalAlert", () => {
  it("renders ticker, z-score, and baseline summary", () => {
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
    expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/z=4.00/)).toBeInTheDocument();
  });
});
