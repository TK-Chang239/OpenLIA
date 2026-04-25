import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { PortfolioHolding, PositionAnalytic } from "../api/portfolio";
import { HoldingsList } from "./HoldingsList";

const mk = (id: string, ticker: string): PortfolioHolding => ({
  id,
  ticker,
  name: "Sample",
  shares: "10",
  cost_basis: "100",
  currency: "USD",
  groups: [],
  notes_text: null,
  added_at: "",
  updated_at: "",
});

function LocationProbe(): JSX.Element {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname + loc.search}</div>;
}

describe("HoldingsList", () => {
  it("renders one row per holding", () => {
    render(
      <MemoryRouter>
        <HoldingsList
          holdings={[mk("1", "AAPL"), mk("2", "MSFT")]}
          analyticsByHolding={new Map()}
          onRemove={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("holding-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("holding-row-MSFT")).toBeInTheDocument();
  });

  it("navigates to ER on row click", () => {
    render(
      <MemoryRouter initialEntries={["/portfolio"]}>
        <Routes>
          <Route
            path="/portfolio"
            element={
              <>
                <HoldingsList
                  holdings={[mk("1", "AAPL")]}
                  analyticsByHolding={new Map()}
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
    fireEvent.click(screen.getByTestId("holding-row-AAPL"));
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/equity-research?ticker=AAPL",
    );
  });

  it("toggles metric badge between $ and %", () => {
    const a: PositionAnalytic = {
      holding_id: "1",
      ticker: "AAPL",
      shares: "10",
      cost_basis: "100",
      last_price: "150",
      market_value: "1500",
      unrealized_pl: "500",
      unrealized_pl_pct: "0.5",
      weight: null,
      currency: "USD",
    };
    render(
      <MemoryRouter>
        <HoldingsList
          holdings={[mk("1", "AAPL")]}
          analyticsByHolding={new Map([["1", a]])}
          onRemove={() => {}}
        />
      </MemoryRouter>,
    );
    const badge = screen.getByTestId("metric-badge-AAPL");
    expect(badge).toHaveTextContent("500");
    fireEvent.click(badge);
    expect(badge).toHaveTextContent("50.00%");
  });

  it("calls onRemove on trash click", () => {
    const onRemove = vi.fn();
    render(
      <MemoryRouter>
        <HoldingsList
          holdings={[mk("1", "AAPL")]}
          analyticsByHolding={new Map()}
          onRemove={onRemove}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByTestId("remove-AAPL"));
    expect(onRemove).toHaveBeenCalledWith("1");
  });
});
