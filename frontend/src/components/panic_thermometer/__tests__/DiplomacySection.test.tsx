import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiplomacySection } from "../sections/DiplomacySection";
import { diplomacyPanel } from "../../../lib/panic_thermometer/copy/panels";

describe("DiplomacySection", () => {
  it("anchors at #diplomacy and renders header chrome", () => {
    const { container } = render(<DiplomacySection panel={diplomacyPanel} />);
    expect(container.querySelector("#diplomacy")).toBeTruthy();
    expect(screen.getByText("D5 · Diplomatic progress")).toBeInTheDocument();
    expect(screen.getByText("Amber · 22/30 days elapsed")).toBeInTheDocument();
  });

  it("renders countdown days remaining and signals counts", () => {
    render(<DiplomacySection panel={diplomacyPanel} />);
    expect(screen.getByText("8 days remaining")).toBeInTheDocument();
    expect(screen.getByText("Progress signals")).toBeInTheDocument();
    expect(screen.getByText("Escalation signals")).toBeInTheDocument();
  });

  it("renders milestone + override action buttons", () => {
    render(<DiplomacySection panel={diplomacyPanel} />);
    expect(screen.getByRole("button", { name: /Mark new milestone/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Override status/ })).toBeInTheDocument();
  });

  it("renders headline news feed entries", () => {
    render(<DiplomacySection panel={diplomacyPanel} />);
    expect(screen.getByText("FT · Middle East")).toBeInTheDocument();
    expect(screen.getByText("Reuters · Energy")).toBeInTheDocument();
  });
});
