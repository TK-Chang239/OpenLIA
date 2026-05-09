import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RsSnapshot, RsSpike } from "../../../api/retail-sentiment";
import { InsightsTab } from "../InsightsTab";

const snap: RsSnapshot = {
  ticker: "AAPL",
  captured_at: new Date().toISOString(),
  sentiment_score: 0.4,
  buzz_volume: 1.5,
  buzz_count: 12,
  sentiment_momentum: 0.1,
  bull_bear_ratio: 2.0,
  buzz_sentiment_divergence: 0.3,
  social_velocity: 0.5,
  cross_source_agreement: 0.8,
  put_call_ratio: null,
  short_interest_pressure: null,
  narrative_concentration: null,
  institutional_retail_gap: null,
  event_sensitivity: null,
  source_breakdown: {},
  narrative: "Strong bullish flow with above-baseline buzz.",
};

const spike: RsSpike = {
  ticker: "AAPL",
  detected_at: new Date().toISOString(),
  buzz: 50,
  baseline_mean: 10,
  baseline_stddev: 2,
  z_score: 4,
};

describe("InsightsTab", () => {
  it("renders narrative paragraph for selected ticker", () => {
    render(
      <InsightsTab selected="AAPL" snapshots={[snap]} spikes={[]} />,
    );
    expect(screen.getByTestId("narrative-paragraph")).toHaveTextContent(
      /bullish flow/i,
    );
  });

  it("renders fallback when narrative is null", () => {
    const empty: RsSnapshot = { ...snap, narrative: null };
    render(
      <InsightsTab selected="AAPL" snapshots={[empty]} spikes={[]} />,
    );
    expect(screen.getByTestId("narrative-paragraph")).toHaveTextContent(
      /no narrative synthesis/i,
    );
  });

  it("renders the active signal alerts", () => {
    render(
      <InsightsTab selected="AAPL" snapshots={[snap]} spikes={[spike]} />,
    );
    expect(screen.getByTestId("signal-AAPL")).toBeInTheDocument();
  });
});
