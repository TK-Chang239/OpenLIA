import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { PortfolioHolding } from "../api/portfolio";
import { ALL_GROUP, } from "./GroupTabs";
import { HoldingsGrid } from "./HoldingsGrid";

const mk = (id: string, ticker: string, groups: string[] = []): PortfolioHolding => ({
  id,
  ticker,
  name: null,
  shares: null,
  cost_basis: null,
  currency: "USD",
  groups,
  notes_text: null,
  added_at: "",
  updated_at: "",
});

function LocationProbe(): JSX.Element {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname + loc.search}</div>;
}

describe("HoldingsGrid", () => {
  it("renders cards for each holding", () => {
    render(
      <MemoryRouter>
        <HoldingsGrid
          holdings={[mk("1", "AAPL"), mk("2", "MSFT")]}
          analyticsByHolding={new Map()}
          activeGroup="Tech"
          onRemove={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("holding-card-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("holding-card-MSFT")).toBeInTheDocument();
  });

  it("sections grouping when on All tab", () => {
    render(
      <MemoryRouter>
        <HoldingsGrid
          holdings={[mk("1", "AAPL", ["Tech"]), mk("2", "JPM", ["Banks"])]}
          analyticsByHolding={new Map()}
          activeGroup={ALL_GROUP}
          onRemove={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Banks/)).toBeInTheDocument();
    expect(screen.getByText(/Tech/)).toBeInTheDocument();
  });

  it("navigates to ER on card click", () => {
    render(
      <MemoryRouter initialEntries={["/p"]}>
        <Routes>
          <Route
            path="/p"
            element={
              <>
                <HoldingsGrid
                  holdings={[mk("1", "AAPL")]}
                  analyticsByHolding={new Map()}
                  activeGroup="Tech"
                  onRemove={() => {}}
                />
                <LocationProbe />
              </>
            }
          />
          <Route path="/equity-research" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByTestId("holding-card-AAPL"));
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/equity-research?ticker=AAPL",
    );
  });

  it("calls onRemove for trash icon", () => {
    const onRemove = vi.fn();
    render(
      <MemoryRouter>
        <HoldingsGrid
          holdings={[mk("1", "AAPL")]}
          analyticsByHolding={new Map()}
          activeGroup="Tech"
          onRemove={onRemove}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByTestId("grid-remove-AAPL"));
    expect(onRemove).toHaveBeenCalledWith("1");
  });
});
