import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FormField } from "./FormField";

describe("FormField", () => {
  it("renders label + input bound via id", () => {
    render(
      <FormField id="email" label="Email">
        <input id="email" />
      </FormField>,
    );
    const label = screen.getByText("Email");
    expect(label.getAttribute("for")).toBe("email");
    expect(screen.getByLabelText("Email")).toBeTruthy();
  });

  it("renders helper text when provided", () => {
    render(
      <FormField id="pw" label="Password" helper="At least 8 chars">
        <input id="pw" />
      </FormField>,
    );
    expect(screen.getByText("At least 8 chars")).toBeTruthy();
  });

  it("renders inline error with aria-describedby wiring", () => {
    render(
      <FormField id="e" label="Email" error="Required">
        <input id="e" />
      </FormField>,
    );
    const err = screen.getByText("Required");
    expect(err.id).toBe("e-error");
  });
});
