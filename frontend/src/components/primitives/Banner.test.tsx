import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Banner } from "./Banner";

describe("Banner", () => {
  it("renders message with error variant by default", () => {
    render(<Banner message="Bad password" />);
    const el = screen.getByRole("alert");
    expect(el.textContent).toContain("Bad password");
    expect(el.className).toMatch(/feedback-error/);
  });

  it("renders success variant with CheckCircle icon", () => {
    render(<Banner message="Saved" variant="success" />);
    const el = screen.getByRole("status");
    expect(el.className).toMatch(/feedback-success/);
  });

  it("renders warning variant", () => {
    render(<Banner message="Slow down" variant="warning" />);
    const el = screen.getByRole("alert");
    expect(el.className).toMatch(/feedback-warning/);
  });
});
