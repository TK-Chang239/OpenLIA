import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RepoEmptyState } from "../RepoEmptyState";

describe("RepoEmptyState", () => {
  it("renders no-saved variant", () => {
    render(<RepoEmptyState mode="no-saved" />);
    expect(screen.getByTestId("repo-empty-no-saved")).toBeInTheDocument();
    expect(screen.getByText(/No saved reports yet/)).toBeInTheDocument();
    expect(screen.getByText(/Save a report from any department/)).toBeInTheDocument();
  });

  it("renders no-match variant with Clear filters action", () => {
    const onClear = vi.fn();
    render(<RepoEmptyState mode="no-match" onClearFilters={onClear} />);
    expect(screen.getByTestId("repo-empty-no-match")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onClear).toHaveBeenCalled();
  });
});
