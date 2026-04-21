import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Input } from "./Input";

describe("Input", () => {
  it("renders with a label and links ids via htmlFor/id", () => {
    render(<Input label="Email" id="email" defaultValue="a@b.com" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveValue("a@b.com");
    expect(input.id).toBe("email");
  });

  it("shows an error message when provided", () => {
    render(<Input label="Email" id="email" error="required" />);
    expect(screen.getByText("required")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });
});
