import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WatchlistRow } from "../WatchlistRow";

describe("WatchlistRow", () => {
  it("renders empty-state when no entries", () => {
    render(
      <WatchlistRow
        entries={[]}
        onAdd={async () => {}}
        onRemove={async () => {}}
      />,
    );
    expect(
      screen.getByText(
        "Add companies to your watchlist to track upcoming earnings",
      ),
    ).toBeInTheDocument();
  });

  it("renders a card per entry", () => {
    const entries = [
      {
        id: "1",
        ticker: "AAPL",
        company_name: "Apple",
        next_earnings_date: "2026-04-25",
        release_timing: "post_market" as const,
      },
      {
        id: "2",
        ticker: "TSLA",
        company_name: "Tesla",
        next_earnings_date: "2026-04-22",
        release_timing: "pre_market" as const,
      },
    ];
    render(
      <WatchlistRow
        entries={entries}
        onAdd={async () => {}}
        onRemove={async () => {}}
      />,
    );
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
  });
});
