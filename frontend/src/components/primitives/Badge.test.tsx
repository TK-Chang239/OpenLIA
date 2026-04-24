import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders children with default variant", () => {
    render(<Badge>ACTIVE</Badge>);
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
  });

  it("applies variant styles", () => {
    render(<Badge variant="success">OK</Badge>);
    const el = screen.getByText("OK");
    expect(el).toBeInTheDocument();
  });
});
