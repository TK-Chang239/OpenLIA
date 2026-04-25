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
    expect(screen.getByRole("button").className).toContain("border-border-secondary");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("renders the fill-wipe overlay only for the primary variant", () => {
    const { rerender } = render(<Button variant="primary">A</Button>);
    const primaryBtn = screen.getByRole("button");
    const wipe = primaryBtn.querySelector("[data-testid='button-fill-wipe']");
    expect(wipe).not.toBeNull();
    expect(wipe!.getAttribute("aria-hidden")).toBe("true");
    expect(wipe!.className).toContain("bg-accent-hover");
    expect(wipe!.className).toContain("-translate-x-full");
    expect(wipe!.className).toContain("group-hover:translate-x-0");

    rerender(<Button variant="secondary">A</Button>);
    expect(
      screen.getByRole("button").querySelector("[data-testid='button-fill-wipe']"),
    ).toBeNull();

    rerender(<Button variant="ghost">A</Button>);
    expect(
      screen.getByRole("button").querySelector("[data-testid='button-fill-wipe']"),
    ).toBeNull();
  });
});
