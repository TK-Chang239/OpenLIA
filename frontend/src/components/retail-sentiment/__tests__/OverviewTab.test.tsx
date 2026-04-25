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
  narrative: null,
};

describe("OverviewTab", () => {
  it("renders heat map when no ticker is selected", () => {
    render(<OverviewTab selected={null} snapshots={[snap]} />);
    expect(screen.getByTestId("rs-heatmap")).toBeInTheDocument();
  });

  it("renders empty state when ticker has no snapshot", () => {
    render(<OverviewTab selected="MSFT" snapshots={[snap]} />);
    expect(screen.getByTestId("overview-empty")).toBeInTheDocument();
  });

  it("renders compact tier when snapshot is found", () => {
    render(<OverviewTab selected="AAPL" snapshots={[snap]} />);
    // Compact tier emits the metric label "Buzz Count" and renders the value
    expect(screen.getByText("Buzz Count")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });
});
