import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders the empty-state copy", () => {
    render(<EmptyState />);
    expect(
      screen.getByText("Your portfolio is empty"),
    ).toBeInTheDocument();
    expect(screen.getByText("Search above to add tickers")).toBeInTheDocument();
  });
});
