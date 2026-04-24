import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SuggestionChips } from "./SuggestionChips";

describe("SuggestionChips", () => {
  it("renders the four static chips plus From Portfolio", () => {
    render(<SuggestionChips onSelect={() => {}} />);
    for (const label of ["AAPL", "TSLA", "NVDA", "MSFT"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(
      screen.getByRole("button", { name: /from portfolio/i })
    ).toBeInTheDocument();
  });

  it("calls onSelect with the chip label when a static chip is clicked", () => {
    const onSelect = vi.fn();
    render(<SuggestionChips onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "AAPL" }));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("opens the portfolio picker and fires onSelect on row click", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [
        { ticker: "GOOG", name: "Alphabet Inc." },
        { ticker: "AMZN", name: "Amazon" },
      ],
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const onSelect = vi.fn();
    render(<SuggestionChips onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /from portfolio/i }));
    await waitFor(() =>
      expect(screen.getByText("GOOG")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByText("GOOG"));
    expect(onSelect).toHaveBeenCalledWith("GOOG");
  });
});
