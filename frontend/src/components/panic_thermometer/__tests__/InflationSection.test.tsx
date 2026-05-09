import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InflationSection } from "../sections/InflationSection";
import { inflationPanel } from "../../../lib/panic_thermometer/copy/panels";

describe("InflationSection", () => {
  it("anchors at #inflation and renders header pill", () => {
    const { container } = render(<InflationSection panel={inflationPanel} />);
    expect(container.querySelector("#inflation")).toBeTruthy();
    expect(screen.getByText("D2 · Inflation expectations")).toBeInTheDocument();
    expect(screen.getByText("Amber · approaching")).toBeInTheDocument();
  });

  it("renders the big value (2.9%) and stamp (+0.2pp m/m)", () => {
    render(<InflationSection panel={inflationPanel} />);
    expect(screen.getAllByText("2.9%").length).toBeGreaterThan(0);
    expect(screen.getByText("+0.2pp m/m")).toBeInTheDocument();
  });

  it("renders the dual-axis legend (TIP price, Michigan 5Y)", () => {
    render(<InflationSection panel={inflationPanel} />);
    expect(screen.getByText(/TIP price/)).toBeInTheDocument();
    expect(screen.getAllByText(/Michigan 5Y/).length).toBeGreaterThan(0);
  });

  it("renders rules including the matched amber rule", () => {
    render(<InflationSection panel={inflationPanel} />);
    expect(screen.getByText("▶ MATCH")).toBeInTheDocument();
  });
});
