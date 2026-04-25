import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FiltersDropdown } from "../FiltersDropdown";

const FACETS = {
  departments: [
    { slug: "equity_research", count: 2 },
    { slug: "secretary", count: 1 },
  ],
  total: 3,
};

describe("FiltersDropdown", () => {
  it("toggles department checks and applies them", async () => {
    const user = userEvent.setup();
    const onApply = vi.fn();
    render(
      <FiltersDropdown
        facets={FACETS}
        selectedDepartments={[]}
        generatedFrom=""
        generatedTo=""
        savedFrom=""
        savedTo=""
        onApply={onApply}
        active={false}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(await screen.findByLabelText(/Equity Research \(2\)/));
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() =>
      expect(onApply).toHaveBeenCalledWith(
        expect.objectContaining({ departments: ["equity_research"] }),
      ),
    );
  });

  it("captures generated date range and forwards on apply", async () => {
    const user = userEvent.setup();
    const onApply = vi.fn();
    render(
      <FiltersDropdown
        facets={FACETS}
        selectedDepartments={[]}
        generatedFrom=""
        generatedTo=""
        savedFrom=""
        savedTo=""
        onApply={onApply}
        active={false}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Filters" }));
    const from = await screen.findByLabelText(/Generated from/);
    await user.type(from, "2026-04-01");
    const to = screen.getByLabelText(/Generated to/);
    await user.type(to, "2026-04-30");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() =>
      expect(onApply).toHaveBeenCalledWith(
        expect.objectContaining({
          generated_from: "2026-04-01",
          generated_to: "2026-04-30",
        }),
      ),
    );
  });

  it("trigger uses accent border when active=true", () => {
    render(
      <FiltersDropdown
        facets={FACETS}
        selectedDepartments={["secretary"]}
        generatedFrom=""
        generatedTo=""
        savedFrom=""
        savedTo=""
        onApply={vi.fn()}
        active={true}
      />,
    );
    const btn = screen.getByRole("button", { name: "Filters" });
    expect(btn.className).toMatch(/border-\[--color-accent-primary\]/);
  });
});
