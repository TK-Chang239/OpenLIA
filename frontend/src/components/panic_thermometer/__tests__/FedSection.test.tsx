import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FedSection } from "../sections/FedSection";
import { fedPanel } from "../../../lib/panic_thermometer/copy/panels";

describe("FedSection", () => {
  it("anchors at the fed id and renders header chrome", () => {
    const { container } = render(<FedSection panel={fedPanel} />);
    expect(container.querySelector("[id='fed']")).toBeTruthy();
    expect(screen.getByText("D3 · Fed language tracker")).toBeInTheDocument();
    expect(screen.getByText("Red · hawkish pivot")).toBeInTheDocument();
  });

  it("renders the big quote and posture timeline", () => {
    render(<FedSection panel={fedPanel} />);
    expect(screen.getByText('"persistent inflation"')).toBeInTheDocument();
    expect(screen.getByText("FOMC posture timeline")).toBeInTheDocument();
  });

  it("renders the headline scanner with sources", () => {
    render(<FedSection panel={fedPanel} />);
    expect(screen.getByText(/Reuters · FOMC Press Conference/)).toBeInTheDocument();
    expect(screen.getByText(/Bloomberg · NY Fed/)).toBeInTheDocument();
  });

  it("renders keyword editor with hawkish matches highlighted", () => {
    render(<FedSection panel={fedPanel} />);
    expect(screen.getByText("Keyword lists · click to edit")).toBeInTheDocument();
    expect(screen.getAllByText("persistent inflation").length).toBeGreaterThan(0);
  });
});
