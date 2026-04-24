import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModeToggle } from "./ModeToggle";

describe("ModeToggle", () => {
  it("renders one button per option and marks the active one", () => {
    render(
      <ModeToggle
        value="b"
        onChange={() => {}}
        options={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
          { value: "c", label: "C" },
        ]}
      />
    );
    expect(screen.getByRole("radio", { name: "B" })).toHaveAttribute(
      "aria-checked",
      "true"
    );
  });

  it("fires onChange when a different option is clicked", () => {
    const onChange = vi.fn();
    render(
      <ModeToggle
        value="a"
        onChange={onChange}
        options={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
        ]}
      />
    );
    fireEvent.click(screen.getByRole("radio", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });
});
