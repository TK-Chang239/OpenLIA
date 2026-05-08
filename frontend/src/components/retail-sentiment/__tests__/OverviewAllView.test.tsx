import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RsSnapshot } from "../../../api/retail-sentiment";
import { OverviewAllView } from "../OverviewAllView";

function makeSnap(overrides: Partial<RsSnapshot>): RsSnapshot {
  return {
    ticker: "AAPL",
    captured_at: new Date().toISOString(),
    sentiment_score: 0.3,
    buzz_volume: 1.2,
    buzz_count: 200,
    sentiment_momentum: 0.05,
    bull_bear_ratio: 0.6,
    buzz_sentiment_divergence: 0.4,
    social_velocity: 0.2,
    cross_source_agreement: 0.7,
    put_call_ratio: null,
    short_interest_pressure: null,
    narrative_concentration: null,
    institutional_retail_gap: null,
    event_sensitivity: null,
    source_breakdown: {},
    narrative: null,
    ...overrides,
  };
}

describe("OverviewAllView", () => {
  it("renders empty state when no snapshots", () => {
    render(
      <OverviewAllView
        snapshots={[]}
        spikes={[]}
        onPickTicker={() => {}}
      />,
    );
    expect(screen.getByTestId("rs-empty-watchlist")).toBeInTheDocument();
  });

  it("renders trending rail and heatmap when snapshots present", () => {
    render(
      <OverviewAllView
        snapshots={[
          makeSnap({ ticker: "AAPL", buzz_volume: 1.6 }),
          makeSnap({ ticker: "MSFT", buzz_volume: 0.9 }),
        ]}
        spikes={[]}
        onPickTicker={() => {}}
      />,
    );
    expect(screen.getByTestId("rs-trending-rail")).toBeInTheDocument();
    expect(screen.getByTestId("rs-heatmap")).toBeInTheDocument();
  });

  it("invokes onPickTicker when a heat row is clicked", () => {
    const onPick = vi.fn();
    render(
      <OverviewAllView
        snapshots={[makeSnap({ ticker: "AAPL" })]}
        spikes={[]}
        onPickTicker={onPick}
      />,
    );
    fireEvent.click(screen.getByTestId("rs-heat-row-AAPL"));
    expect(onPick).toHaveBeenCalledWith("AAPL");
  });
});
