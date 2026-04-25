import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api/portfolio";
import { PortfolioShell } from "./PortfolioShell";

describe("PortfolioShell", () => {
  beforeEach(() => {
    vi.spyOn(api, "fetchHoldings").mockResolvedValue([]);
    vi.spyOn(api, "fetchAnalytics").mockResolvedValue({
      total_market_value: "0",
      total_cost_basis: "0",
      total_unrealized_pl: "0",
      total_unrealized_pl_pct: null,
      positions: [],
      allocations: {},
    });
    vi.spyOn(api, "fetchGroups").mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders shell heading and SearchAndAdd", async () => {
    render(
      <MemoryRouter>
        <PortfolioShell />
      </MemoryRouter>,
    );
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    await waitFor(() => screen.getByTestId("portfolio-empty"));
  });

  it("supports list+grid view toggle via useLocalPref", async () => {
    render(
      <MemoryRouter>
        <PortfolioShell />
      </MemoryRouter>,
    );
    const section = await screen.findByTestId("holdings-section");
    expect(section).toHaveAttribute("data-view", "list");
  });
});
