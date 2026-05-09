import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScorecardGrid } from "../sections/ScorecardGrid";
import { scorecards } from "../../../lib/panic_thermometer/copy/summary";

describe("ScorecardGrid", () => {
  it("renders all 5 scorecards with anchor hrefs", () => {
    render(<ScorecardGrid entries={scorecards} />);
    for (const card of scorecards) {
      const a = screen.getByTestId(`pt-scorecard-${card.panelId}`);
      expect(a).toHaveAttribute("href", `#${card.panelId}`);
      expect(a).toHaveTextContent(card.title);
    }
  });

  it("emits the section header with panel count", () => {
    render(<ScorecardGrid entries={scorecards} />);
    expect(screen.getByText("Indicator scorecards")).toBeInTheDocument();
    expect(screen.getByText("5 panels · click to drill in")).toBeInTheDocument();
  });

  it("renders status stamps for each card", () => {
    render(<ScorecardGrid entries={scorecards} />);
    expect(screen.getAllByText("Red").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Amber").length).toBeGreaterThan(0);
    expect(screen.getByText("Dark red")).toBeInTheDocument();
  });
});
