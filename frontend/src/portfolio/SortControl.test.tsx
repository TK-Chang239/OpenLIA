import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SortControl } from "./SortControl";

describe("SortControl", () => {
  it("calls onChange with the new sort key", () => {
    const onChange = vi.fn();
    render(<SortControl value="alpha-asc" onChange={onChange} />);
    fireEvent.change(screen.getByTestId("sort-control"), {
      target: { value: "price-desc" },
    });
    expect(onChange).toHaveBeenCalledWith("price-desc");
  });
});
