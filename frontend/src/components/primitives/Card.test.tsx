import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card } from "./Card";

describe("Card", () => {
  it("renders children inside a region", () => {
    render(<Card aria-label="section"><p>hi</p></Card>);
    expect(screen.getByRole("region", { name: "section" })).toContainHTML("<p>hi</p>");
  });
});
