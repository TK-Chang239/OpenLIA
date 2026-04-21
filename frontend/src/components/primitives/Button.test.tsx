import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children and fires onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    screen.getByRole("button", { name: "Save" }).click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("applies primary and secondary variants", () => {
    const { rerender } = render(<Button variant="primary">A</Button>);
    expect(screen.getByRole("button").className).toContain("bg-accent-primary");
    rerender(<Button variant="secondary">A</Button>);
    expect(screen.getByRole("button").className).toContain("bg-surface-hover");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
