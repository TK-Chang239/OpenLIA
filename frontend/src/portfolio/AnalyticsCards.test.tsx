import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalyticsCards } from "./AnalyticsCards";

describe("AnalyticsCards", () => {
  it("renders dashes when analytics is null", () => {
    render(<AnalyticsCards analytics={null} />);
    expect(screen.getByText("Market Value")).toBeInTheDocument();
  });

  it("renders positive P/L with success color", () => {
    render(
      <AnalyticsCards
        analytics={{
          total_market_value: "1000",
          total_cost_basis: "800",
          total_unrealized_pl: "200",
          total_unrealized_pl_pct: "0.25",
          positions: [],
          allocations: { AAPL: "0.6", MSFT: "0.4" },
        }}
      />,
    );
    expect(screen.getByTestId("pl-value")).toHaveTextContent("200");
    expect(screen.getByTestId("allocation-chart")).toBeInTheDocument();
  });
});
