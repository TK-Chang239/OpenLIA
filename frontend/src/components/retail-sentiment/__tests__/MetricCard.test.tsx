import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "../MetricCard";

describe("MetricCard", () => {
  it("renders label and formatted numeric value", () => {
    render(<MetricCard label="Sentiment" value={0.42} />);
    expect(screen.getByText("Sentiment")).toBeInTheDocument();
    expect(screen.getByText("0.42")).toBeInTheDocument();
  });

  it("falls back to em-dash when value is null", () => {
    render(<MetricCard label="Put/Call" value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders reliability badge when supplied", () => {
    render(
      <MetricCard label="Buzz" value={1.5} reliability="medium" />,
    );
    expect(screen.getByTestId("reliability-medium")).toBeInTheDocument();
  });
});
