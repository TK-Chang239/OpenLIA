import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SectionRow } from "../SectionRow";

describe("SectionRow", () => {
  it("renders title and hint", () => {
    render(
      <SectionRow
        id="x"
        title="Macro"
        hint="Macro hint"
        checked={false}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText("Macro")).toBeInTheDocument();
    expect(screen.getByText("Macro hint")).toBeInTheDocument();
  });

  it("toggles checked via aria-checked button", () => {
    const onChange = vi.fn();
    render(
      <SectionRow
        id="x"
        title="Macro"
        checked={false}
        onChange={onChange}
      />,
    );
    const cb = screen.getByRole("checkbox");
    expect(cb).toHaveAttribute("aria-checked", "false");
    fireEvent.click(cb);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});
