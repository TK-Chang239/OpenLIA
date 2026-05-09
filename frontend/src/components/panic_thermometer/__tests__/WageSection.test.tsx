import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WageSection } from "../sections/WageSection";
import { wagePanel } from "../../../lib/panic_thermometer/copy/panels";

describe("WageSection", () => {
  it("anchors at #wage and renders header chrome", () => {
    const { container } = render(<WageSection panel={wagePanel} />);
    expect(container.querySelector("#wage")).toBeTruthy();
    expect(screen.getByText("D4 · Wage growth")).toBeInTheDocument();
    expect(screen.getByText("Dark red · 2 consecutive")).toBeInTheDocument();
  });

  it("renders big value (+0.6%) and consecutive bracket label", () => {
    render(<WageSection panel={wagePanel} />);
    expect(screen.getByText("+0.6%")).toBeInTheDocument();
    expect(screen.getByText("2nd consecutive hot print")).toBeInTheDocument();
    expect(screen.getByText("2 consecutive · spiral")).toBeInTheDocument();
  });

  it("renders threshold labels for amber and red", () => {
    render(<WageSection panel={wagePanel} />);
    expect(screen.getByText(/0.4% — amber/)).toBeInTheDocument();
    expect(screen.getByText(/0.5% — red/)).toBeInTheDocument();
  });

  it("renders param rows including consecutive_required", () => {
    render(<WageSection panel={wagePanel} />);
    expect(screen.getByText("consecutive_required")).toBeInTheDocument();
    expect(screen.getByText("avg_12m")).toBeInTheDocument();
  });
});
