import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import "../../../../i18n";
import { EuViewToggle } from "../EuViewToggle";

describe("EuViewToggle", () => {
  it("renders both view tabs and marks the active one selected", () => {
    render(<EuViewToggle view="stream" onChange={() => {}} />);
    const stream = screen.getByRole("tab", { name: /stream/i });
    const calendar = screen.getByRole("tab", { name: /calendar/i });
    expect(stream).toHaveAttribute("aria-selected", "true");
    expect(calendar).toHaveAttribute("aria-selected", "false");
  });

  it("calls onChange with the clicked view", () => {
    const onChange = vi.fn();
    render(<EuViewToggle view="stream" onChange={onChange} />);
    fireEvent.click(screen.getByRole("tab", { name: /calendar/i }));
    expect(onChange).toHaveBeenCalledWith("calendar");
  });
});
