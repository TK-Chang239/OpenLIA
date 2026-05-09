import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VerdictBlock } from "../sections/VerdictBlock";
import { verdictCopy } from "../../../lib/panic_thermometer/copy/verdict";

describe("VerdictBlock", () => {
  it("renders the section label with confidence", () => {
    render(<VerdictBlock verdict={verdictCopy} />);
    expect(screen.getByText("LIA · verdict")).toBeInTheDocument();
    expect(screen.getByText("06:42 · confidence 78")).toBeInTheDocument();
  });

  it("renders LIA badge and headline", () => {
    render(<VerdictBlock verdict={verdictCopy} />);
    expect(screen.getByText("LIA")).toBeInTheDocument();
    expect(
      screen.getByText(/wage-Fed loop is the actionable signal/),
    ).toBeInTheDocument();
  });

  it("renders the cross-reference tags with hrefs", () => {
    render(<VerdictBlock verdict={verdictCopy} />);
    const wageTag = screen.getByText("→ D4 Wage panel");
    expect(wageTag.closest("a")).toHaveAttribute("href", "#wage");
    const macroTag = screen.getByText("→ Cross-check Macro Research summary");
    expect(macroTag.closest("a")).toHaveAttribute("href", "/macro-research");
  });

  it("uses severe variant by default", () => {
    const { container } = render(<VerdictBlock verdict={verdictCopy} />);
    expect(container.querySelector(".pt-verdict.is-severe")).toBeTruthy();
  });
});
