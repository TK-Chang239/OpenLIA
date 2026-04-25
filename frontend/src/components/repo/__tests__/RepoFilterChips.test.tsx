import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RepoFilterChips } from "../RepoFilterChips";

const noop = () => {};

describe("RepoFilterChips", () => {
  it("renders nothing when no filters active", () => {
    const { container } = render(
      <RepoFilterChips
        q=""
        departments={[]}
        generatedFrom=""
        generatedTo=""
        savedFrom=""
        savedTo=""
        onRemoveSearch={noop}
        onRemoveDepartment={noop}
        onRemoveGeneratedRange={noop}
        onRemoveSavedRange={noop}
        onClearAll={noop}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows search and department chips and dispatches dismiss callbacks", () => {
    const onRemoveSearch = vi.fn();
    const onRemoveDepartment = vi.fn();
    const onClearAll = vi.fn();
    render(
      <RepoFilterChips
        q="aapl"
        departments={["equity_research"]}
        generatedFrom=""
        generatedTo=""
        savedFrom=""
        savedTo=""
        onRemoveSearch={onRemoveSearch}
        onRemoveDepartment={onRemoveDepartment}
        onRemoveGeneratedRange={noop}
        onRemoveSavedRange={noop}
        onClearAll={onClearAll}
      />,
    );
    expect(screen.getByText('Search: "aapl"')).toBeInTheDocument();
    expect(screen.getByText("Equity Research")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Remove filter Search/ }));
    expect(onRemoveSearch).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /Remove filter Equity Research/ }));
    expect(onRemoveDepartment).toHaveBeenCalledWith("equity_research");
    fireEvent.click(screen.getByText("Clear all"));
    expect(onClearAll).toHaveBeenCalledTimes(1);
  });

  it("shows generated and saved range chips", () => {
    render(
      <RepoFilterChips
        q=""
        departments={[]}
        generatedFrom="2026-04-01"
        generatedTo="2026-04-30"
        savedFrom="2026-04-10"
        savedTo=""
        onRemoveSearch={noop}
        onRemoveDepartment={noop}
        onRemoveGeneratedRange={noop}
        onRemoveSavedRange={noop}
        onClearAll={noop}
      />,
    );
    expect(screen.getByText(/Generated: 2026-04-01 . 2026-04-30/)).toBeInTheDocument();
    expect(screen.getByText(/Saved: from 2026-04-10/)).toBeInTheDocument();
  });
});
