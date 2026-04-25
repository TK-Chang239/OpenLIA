import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SentimentGauge } from "../SentimentGauge";

describe("SentimentGauge", () => {
  it("renders the score with two decimals", () => {
    render(<SentimentGauge score={0.732} />);
    expect(screen.getByText("0.73")).toBeInTheDocument();
  });

  it("clamps to [-1, 1]", () => {
    render(<SentimentGauge score={5} />);
    expect(screen.getByText("1.00")).toBeInTheDocument();
  });

  it("has an accessible label", () => {
    render(<SentimentGauge score={-0.5} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "aria-label",
      expect.stringContaining("-0.50"),
    );
  });
});
