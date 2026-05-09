import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OilSection } from "../sections/OilSection";
import { oilPanel } from "../../../lib/panic_thermometer/copy/panels";

describe("OilSection", () => {
  it("anchors at #oil and renders header chrome", () => {
    const { container } = render(<OilSection panel={oilPanel} />);
    expect(container.querySelector("#oil")).toBeTruthy();
    expect(screen.getByText("D1 · Oil price duration")).toBeInTheDocument();
    expect(screen.getByText("Red · 47d streak")).toBeInTheDocument();
    expect(screen.getByText("Updated 06:30")).toBeInTheDocument();
  });

  it("renders big value, narrative, and streak progression", () => {
    render(<OilSection panel={oilPanel} />);
    expect(screen.getByText("$48.20")).toBeInTheDocument();
    expect(screen.getByText("Above $45.00")).toBeInTheDocument();
    expect(screen.getByText("Streak progression")).toBeInTheDocument();
    expect(screen.getByText(/2022 trigger/)).toBeInTheDocument();
  });

  it("renders rule set with one match row", () => {
    render(<OilSection panel={oilPanel} />);
    expect(screen.getByText("▶ MATCH")).toBeInTheDocument();
  });

  it("renders param rows for ticker, price_threshold, and streak windows", () => {
    render(<OilSection panel={oilPanel} />);
    expect(screen.getByText("ticker")).toBeInTheDocument();
    expect(screen.getByText("price_threshold")).toBeInTheDocument();
    expect(screen.getByText("streak_red")).toBeInTheDocument();
  });
});
