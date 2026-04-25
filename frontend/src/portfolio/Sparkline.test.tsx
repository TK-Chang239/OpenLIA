import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sparkline } from "./Sparkline";

describe("Sparkline", () => {
  it("renders an em-dash placeholder for empty data", () => {
    render(<Sparkline values={[]} />);
    expect(screen.getByTestId("sparkline-empty")).toHaveTextContent("—");
  });

  it("renders an SVG polyline when there are at least two points", () => {
    render(<Sparkline values={[1, 2, 3]} />);
    const svg = screen.getByTestId("sparkline");
    expect(svg.querySelector("polyline")).not.toBeNull();
  });
});
