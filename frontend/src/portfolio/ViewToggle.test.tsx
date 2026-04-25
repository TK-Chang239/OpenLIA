import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ViewToggle } from "./ViewToggle";

describe("ViewToggle", () => {
  it("toggles between list and grid", () => {
    const onChange = vi.fn();
    render(<ViewToggle value="list" onChange={onChange} />);
    fireEvent.click(screen.getByTestId("view-toggle-grid"));
    expect(onChange).toHaveBeenCalledWith("grid");
  });

  it("marks current view as selected", () => {
    render(<ViewToggle value="grid" onChange={() => {}} />);
    expect(screen.getByTestId("view-toggle-grid")).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
