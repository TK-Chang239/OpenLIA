import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PasswordStrengthMeter } from "./PasswordStrengthMeter";

describe("PasswordStrengthMeter", () => {
  it("renders nothing when value is empty", () => {
    const { container } = render(<PasswordStrengthMeter value="" />);
    expect(container.firstChild).toBeNull();
  });

  it("labels 'Weak' when length < 8", () => {
    render(<PasswordStrengthMeter value="abc" />);
    expect(screen.getByText("Weak")).toBeTruthy();
  });

  it("labels 'Fair' at 2 classes", () => {
    render(<PasswordStrengthMeter value="abcdefgH" />);
    expect(screen.getByText("Fair")).toBeTruthy();
  });

  it("labels 'Good' at 3 classes", () => {
    render(<PasswordStrengthMeter value="Abcdefg1" />);
    expect(screen.getByText("Good")).toBeTruthy();
  });

  it("labels 'Strong' at 4 classes", () => {
    render(<PasswordStrengthMeter value="Abcdefg1!" />);
    expect(screen.getByText("Strong")).toBeTruthy();
  });
});
