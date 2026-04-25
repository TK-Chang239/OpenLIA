import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/portfolio";
import { SearchAndAdd } from "./SearchAndAdd";

describe("SearchAndAdd", () => {
  beforeEach(() => {
    vi.spyOn(api, "searchTickers").mockResolvedValue([
      { ticker: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
    ]);
    vi.spyOn(api, "createHolding").mockResolvedValue({
      id: "1",
      ticker: "AAPL",
      name: null,
      shares: null,
      cost_basis: null,
      currency: "USD",
      groups: [],
      notes_text: null,
      added_at: "",
      updated_at: "",
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses combobox role with aria-expanded", () => {
    render(
      <SearchAndAdd groups={[]} existingTickers={new Set()} onAdded={() => {}} />,
    );
    const input = screen.getByRole("combobox");
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("debounces and shows results after 300ms", async () => {
    render(
      <SearchAndAdd groups={[]} existingTickers={new Set()} onAdded={() => {}} />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "aapl" } });
    expect(api.searchTickers).not.toHaveBeenCalled();
    await waitFor(
      () => expect(api.searchTickers).toHaveBeenCalled(),
      { timeout: 1500 },
    );
    await screen.findByTestId("search-results");
  });

  it("shows already-added rows as non-actionable", async () => {
    vi.mocked(api.searchTickers).mockResolvedValueOnce([
      { ticker: "AAPL", name: "Apple", already_added: true },
    ]);
    render(
      <SearchAndAdd
        groups={[]}
        existingTickers={new Set(["AAPL"])}
        onAdded={() => {}}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "a" } });
    const row = await screen.findByTestId("search-row-AAPL", {}, { timeout: 1500 });
    expect(row).toHaveAttribute("data-already-added", "true");
    fireEvent.mouseDown(row);
    expect(api.createHolding).not.toHaveBeenCalled();
  });

  it("opens the group-assignment popup when a row is chosen", async () => {
    render(
      <SearchAndAdd
        groups={["Tech"]}
        existingTickers={new Set()}
        onAdded={() => {}}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "a" } });
    const row = await screen.findByTestId("search-row-AAPL", {}, { timeout: 1500 });
    fireEvent.mouseDown(row);
    await screen.findByTestId("group-assign-popup");
    expect(screen.getByText(/Assign AAPL/)).toBeInTheDocument();
  });
});
