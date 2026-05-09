import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RepoFilterBar } from "../RepoFilterBar";

const FACETS = { departments: [], total: 0 };

describe("RepoFilterBar", () => {
  it("renders search input and filters trigger", () => {
    render(
      <RepoFilterBar
        q=""
        onQChange={vi.fn()}
        facets={FACETS}
        selectedDepartments={[]}
        generatedFrom=""
        generatedTo=""
        savedFrom=""
        savedTo=""
        filtersActive={false}
        activeFilterCount={0}
        onApplyFilters={vi.fn()}
      />,
    );
    expect(screen.getByLabelText(/Search filename/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Filters" })).toBeInTheDocument();
  });

  it("forwards search input changes", () => {
    const onQ = vi.fn();
    render(
      <RepoFilterBar
        q=""
        onQChange={onQ}
        facets={FACETS}
        selectedDepartments={[]}
        generatedFrom=""
        generatedTo=""
        savedFrom=""
        savedTo=""
        filtersActive={false}
        activeFilterCount={0}
        onApplyFilters={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Search filename/), { target: { value: "msft" } });
    expect(onQ).toHaveBeenCalledWith("msft");
  });
});
