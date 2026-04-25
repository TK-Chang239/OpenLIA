import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card } from "./Card";

describe("Card", () => {
  it("renders children inside a region", () => {
    render(<Card aria-label="section"><p>hi</p></Card>);
    expect(screen.getByRole("region", { name: "section" })).toContainHTML("<p>hi</p>");
  });

  it("renders the yellow accent bar as aria-hidden span", () => {
    render(<Card aria-label="bar"><p>x</p></Card>);
    const region = screen.getByRole("region", { name: "bar" });
    const bar = region.querySelector("[aria-hidden='true']");
    expect(bar).not.toBeNull();
    expect(bar!.className).toContain("bg-accent-primary");
  });

  it("composes hover translate + olive border classes on the wrapper", () => {
    render(<Card aria-label="hover"><p>x</p></Card>);
    const region = screen.getByRole("region", { name: "hover" });
    expect(region.className).toContain("hover:-translate-y-1");
    expect(region.className).toContain("hover:border-yellow-600");
  });

  it("does not apply a default box-shadow", () => {
    render(<Card aria-label="noshadow"><p>x</p></Card>);
    const region = screen.getByRole("region", { name: "noshadow" });
    expect(region.className).not.toMatch(/(^|\s)shadow-/);
  });
});
