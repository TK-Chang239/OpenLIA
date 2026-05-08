import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SentimentGauge } from "../SentimentGauge";

describe("SentimentGauge", () => {
  it("renders the score with two decimals on signed scale", () => {
    render(<SentimentGauge score={0.732} scale="signed" />);
    expect(screen.getByText("0.73")).toBeInTheDocument();
  });

  it("clamps to [-1, 1] on signed scale", () => {
    render(<SentimentGauge score={5} scale="signed" />);
    expect(screen.getByText("1.00")).toBeInTheDocument();
  });

  it("auto-detects percent scale for values outside [-1, 1]", () => {
    render(<SentimentGauge score={71} />);
    expect(screen.getByText("71")).toBeInTheDocument();
  });

  it("has an accessible label including the regime", () => {
    render(<SentimentGauge score={-0.5} scale="signed" />);
    expect(screen.getByTestId("sentiment-gauge")).toHaveAttribute(
      "aria-label",
      expect.stringContaining("-0.50"),
    );
  });

  it("renders an em-dash when score is null", () => {
    render(<SentimentGauge score={null} />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
