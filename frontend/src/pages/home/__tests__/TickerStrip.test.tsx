import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { TickerStrip } from "../TickerStrip";
import * as marketsApi from "../../../api/markets";
import type { IndexQuote } from "../../../api/markets";

vi.mock("../../../api/markets", () => ({ fetchMarketIndices: vi.fn() }));

const mocked = marketsApi as unknown as {
  fetchMarketIndices: ReturnType<typeof vi.fn>;
};

function quote(overrides: Partial<IndexQuote> = {}): IndexQuote {
  return {
    symbol: "GSPC.INDX",
    label: "S&P 500",
    value: 7757.64,
    previous_close: 7709.96,
    change_abs: 47.68,
    change_pct: 0.62,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TickerStrip", () => {
  it("renders live index cells with value and delta", async () => {
    mocked.fetchMarketIndices.mockResolvedValue({
      available: true,
      indices: [
        quote(),
        quote({
          symbol: "US10Y.GBOND",
          label: "10Y",
          value: 4.651,
          change_pct: null, // no intraday delta -> no delta shown
        }),
      ],
    });
    render(<TickerStrip />);
    expect(await screen.findByText("S&P 500")).toBeInTheDocument();
    // Large index level gets thousands separators, no decimals.
    expect(screen.getByText("7,758")).toBeInTheDocument();
    expect(screen.getByText("+0.62%")).toBeInTheDocument();
    // 10Y small value keeps 2 decimals and shows no delta.
    expect(screen.getByText("4.65")).toBeInTheDocument();
  });

  it("shows a connect-EODHD hint when no EODHD connector is configured", async () => {
    mocked.fetchMarketIndices.mockResolvedValue({ available: false, indices: [] });
    render(<TickerStrip />);
    expect(
      await screen.findByText(/connect eodhd to see market indices/i),
    ).toBeInTheDocument();
  });

  it("renders nothing when the fetch fails", async () => {
    mocked.fetchMarketIndices.mockRejectedValue(new Error("boom"));
    const { container } = render(<TickerStrip />);
    await waitFor(() => expect(mocked.fetchMarketIndices).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
