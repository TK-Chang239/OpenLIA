import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SortDropdown } from "../SortDropdown";

describe("SortDropdown", () => {
  it("renders trigger label using provided value", () => {
    render(<SortDropdown value="saved_desc" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Sort/ })).toHaveTextContent(
      "Sort: Date Saved (newest)",
    );
  });

  it("invokes onChange when an option is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SortDropdown value="saved_desc" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /Sort/ }));
    await user.click(await screen.findByText("Filename (A→Z)"));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("filename_asc"));
  });

  it("marks the active option with the Check icon", async () => {
    const user = userEvent.setup();
    render(<SortDropdown value="filename_asc" onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Sort/ }));
    const items = await screen.findAllByRole("menuitem");
    const active = items.find((el) => el.getAttribute("data-active") === "true");
    expect(active?.textContent).toMatch(/Filename/);
  });
});
