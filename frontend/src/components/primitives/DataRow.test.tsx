import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataRow } from "./DataRow";

describe("DataRow", () => {
  it("renders label and value with ol-label + tabular-nums", () => {
    render(<DataRow label="Price" value="123.45" />);
    const label = screen.getByText("Price");
    expect(label.className).toContain("ol-label");
    const value = screen.getByText("123.45");
    expect(value.className).toContain("tabular-nums");
  });

  it("renders delta as success color when deltaDirection='pos'", () => {
    render(<DataRow label="P" value="1" delta="+1.2%" deltaDirection="pos" />);
    const delta = screen.getByText("+1.2%");
    expect(delta.getAttribute("style")).toContain(
      "var(--color-feedback-success)",
    );
  });

  it("renders delta as error color when deltaDirection='neg'", () => {
    render(<DataRow label="P" value="1" delta="-1.2%" deltaDirection="neg" />);
    const delta = screen.getByText("-1.2%");
    expect(delta.getAttribute("style")).toContain(
      "var(--color-feedback-error)",
    );
  });
});
