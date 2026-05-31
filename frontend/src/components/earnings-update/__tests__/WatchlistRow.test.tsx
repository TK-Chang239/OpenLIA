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
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "2",
        ticker: "TSLA",
        company_name: "Tesla",
        created_at: "2026-01-01T00:00:00Z",
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
