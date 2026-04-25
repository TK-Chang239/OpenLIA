import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RsSnapshot } from "../../../api/retail-sentiment";
import { EvidenceTab } from "../EvidenceTab";

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
  narrative_concentration: 0.45,
  institutional_retail_gap: null,
  event_sensitivity: null,
  source_breakdown: {},
  narrative: null,
};

describe("EvidenceTab", () => {
  it("prompts for ticker when none selected", () => {
    render(<EvidenceTab selected={null} history={[]} />);
    expect(
      screen.getByText(/Select a single ticker/i),
    ).toBeInTheDocument();
  });

  it("renders empty state when history is empty", () => {
    render(<EvidenceTab selected="AAPL" history={[]} />);
    expect(screen.getByTestId("evidence-empty")).toBeInTheDocument();
  });

  it("renders decomposition + feed when history present", () => {
    render(<EvidenceTab selected="AAPL" history={[snap]} />);
    expect(screen.getByTestId("evidence-decomposition")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-feed")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-filter")).toBeInTheDocument();
  });
});
