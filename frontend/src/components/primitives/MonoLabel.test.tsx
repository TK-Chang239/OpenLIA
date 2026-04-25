import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MonoLabel } from "./MonoLabel";

describe("MonoLabel", () => {
  it("renders children inside a span with ol-label class", () => {
    render(<MonoLabel>HELLO</MonoLabel>);
    const span = screen.getByText("HELLO");
    expect(span.tagName).toBe("SPAN");
    expect(span.className).toContain("ol-label");
  });

  it("forwards arbitrary props (data-testid)", () => {
    render(<MonoLabel data-testid="m">VAL</MonoLabel>);
    expect(screen.getByTestId("m")).toBeInTheDocument();
  });
});
