import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RsSnapshot } from "../../../api/retail-sentiment";
import { RS_METRIC_CATALOG } from "../../../lib/retail-sentiment/metric-catalog";
import { MetricsDeepDiveTab } from "../MetricsDeepDiveTab";

function makeSnap(captured_at: string, override: Partial<RsSnapshot> = {}): RsSnapshot {
  return {
    ticker: "AAPL",
    captured_at,
    sentiment_score: 0.3,
    buzz_volume: 1.2,
    buzz_count: 100,
    sentiment_momentum: 0.05,
    bull_bear_ratio: 0.6,
    buzz_sentiment_divergence: 0.4,
    social_velocity: 0.1,
    cross_source_agreement: 0.7,
    put_call_ratio: null,
    short_interest_pressure: null,
    narrative_concentration: null,
    institutional_retail_gap: null,
    event_sensitivity: null,
    source_breakdown: {},
    narrative: null,
    ...override,
  };
}

const history: RsSnapshot[] = [
  makeSnap("2026-05-01T12:00:00Z"),
  makeSnap("2026-05-02T12:00:00Z", { sentiment_score: 0.4, buzz_volume: 1.6 }),
  makeSnap("2026-05-03T12:00:00Z", { sentiment_score: 0.5, buzz_volume: 1.1 }),
];

describe("MetricsDeepDiveTab", () => {
  it("renders an empty-state when no ticker selected", () => {
    render(<MetricsDeepDiveTab selected={null} history={[]} />);
    expect(screen.getByTestId("deep-dive-empty-selection")).toBeInTheDocument();
  });

  it("renders one section per metric in the catalog", () => {
    render(<MetricsDeepDiveTab selected="AAPL" history={history} />);
    for (const m of RS_METRIC_CATALOG) {
      expect(screen.getByTestId(`deep-dive-${m.id}`)).toBeInTheDocument();
    }
  });

  it("renders the metric-specific chart for buzz volume", () => {
    render(<MetricsDeepDiveTab selected="AAPL" history={history} />);
    expect(screen.getByTestId("buzz-bars")).toBeInTheDocument();
  });

  it("renders the dual-fill area chart for momentum", () => {
    render(<MetricsDeepDiveTab selected="AAPL" history={history} />);
    expect(screen.getByTestId("momentum-area")).toBeInTheDocument();
  });

  it("renders the divergence bars", () => {
    render(<MetricsDeepDiveTab selected="AAPL" history={history} />);
    expect(screen.getByTestId("divergence-bars")).toBeInTheDocument();
  });

  it("falls back to no-history block when a metric has no values", () => {
    render(<MetricsDeepDiveTab selected="AAPL" history={history} />);
    // put_call_ratio is null on every snap above
    expect(
      screen.getByTestId("deep-dive-empty-put_call_ratio"),
    ).toBeInTheDocument();
  });

  it("shows the formula for each metric", () => {
    render(<MetricsDeepDiveTab selected="AAPL" history={history} />);
    expect(
      screen.getByText(
        /\(positive_mentions − negative_mentions\) \/ total_mentions/i,
      ),
    ).toBeInTheDocument();
  });
});
