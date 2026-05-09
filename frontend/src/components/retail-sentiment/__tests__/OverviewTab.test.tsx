import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RsSnapshot } from "../../../api/retail-sentiment";
import { OverviewTab } from "../OverviewTab";

const snap: RsSnapshot = {
  ticker: "AAPL",
  captured_at: new Date().toISOString(),
  sentiment_score: 0.4,
  buzz_volume: 1.5,
  buzz_count: 12,
  sentiment_momentum: 0.1,
  bull_bear_ratio: 0.65,
  buzz_sentiment_divergence: 0.3,
  social_velocity: 0.5,
  cross_source_agreement: 0.8,
  put_call_ratio: null,
  short_interest_pressure: null,
  narrative_concentration: null,
  institutional_retail_gap: null,
  event_sensitivity: null,
  source_breakdown: { eodhd_news: 220, social_media: 1180 },
  narrative: "Bullish lean with elevated buzz.",
};

describe("OverviewTab single-ticker", () => {
  it("renders the hero, narrative, and compact tier", () => {
    render(
      <OverviewTab selected="AAPL" snapshot={snap} history={[snap]} />,
    );
    expect(screen.getByTestId("overview-single")).toBeInTheDocument();
    expect(screen.getByTestId("rs-hero")).toBeInTheDocument();
    expect(screen.getByTestId("rs-lia-take")).toHaveTextContent(
      /Bullish lean/i,
    );
    expect(screen.getByTestId("rs-compact-tier")).toBeInTheDocument();
  });

  it("renders the sentiment gauge", () => {
    render(
      <OverviewTab selected="AAPL" snapshot={snap} history={[snap]} />,
    );
    expect(screen.getByTestId("sentiment-gauge")).toBeInTheDocument();
  });

  it("renders the sentiment vs price overlay with quote data", () => {
    const captured_at = "2026-05-03T12:00:00Z";
    render(
      <OverviewTab
        selected="AAPL"
        snapshot={{ ...snap, captured_at }}
        history={[{ ...snap, captured_at }]}
        quotes={[
          {
            date: "2026-05-03",
            close: 200.5,
            daily_change_pct: 0.5,
            cumulative_pct: 1.2,
          },
        ]}
      />,
    );
    expect(screen.getByTestId("sentiment-price-overlay")).toBeInTheDocument();
    expect(screen.getByText(/price \+1\.20%/)).toBeInTheDocument();
  });

  it("shows awaiting-key copy when quote data missing", () => {
    render(
      <OverviewTab
        selected="AAPL"
        snapshot={snap}
        history={[snap]}
        quotes={[]}
      />,
    );
    expect(
      screen.getByText(/price overlay awaiting EODHD key/i),
    ).toBeInTheDocument();
  });

  it("falls back to placeholder text when snapshot has no narrative", () => {
    render(
      <OverviewTab
        selected="AAPL"
        snapshot={{ ...snap, narrative: null }}
        history={[snap]}
      />,
    );
    expect(screen.getAllByText(/No narrative/i).length).toBeGreaterThan(0);
  });
});
