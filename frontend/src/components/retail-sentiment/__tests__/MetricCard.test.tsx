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

  it("renders units when supplied and value is present", () => {
    render(<MetricCard label="Buzz" value={1.5} units="× 30d" />);
    expect(screen.getByText("× 30d")).toBeInTheDocument();
  });

  it("applies disabled note when value is null", () => {
    render(
      <MetricCard label="Gap" value={null} disabledNote="Provider not configured." />,
    );
    expect(screen.getByText("Provider not configured.")).toBeInTheDocument();
  });
});
