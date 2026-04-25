import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AreaChart } from "./AreaChart";

describe("AreaChart", () => {
  it("renders empty placeholder for less than 2 points", () => {
    render(<AreaChart values={[1]} />);
    expect(screen.getByTestId("area-empty")).toBeInTheDocument();
  });

  it("renders SVG paths for valid series", () => {
    const { container } = render(<AreaChart values={[1, 2, 3, 4]} />);
    const svg = screen.getByTestId("area-chart");
    expect(svg).toBeInTheDocument();
    expect(container.querySelectorAll("path").length).toBeGreaterThanOrEqual(2);
  });
});
