import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RsSnapshot } from "../../../api/retail-sentiment";
import { EvidenceTab } from "../EvidenceTab";

function makeSnap(override: Partial<RsSnapshot> = {}): RsSnapshot {
  return {
    ticker: "AAPL",
    captured_at: "2026-05-03T12:00:00Z",
    sentiment_score: 0.4,
    buzz_volume: 1.5,
    buzz_count: 12,
    sentiment_momentum: 0.1,
    bull_bear_ratio: 0.6,
    buzz_sentiment_divergence: 0.3,
    social_velocity: 0.5,
    cross_source_agreement: 0.8,
    put_call_ratio: null,
    short_interest_pressure: null,
    narrative_concentration: 0.45,
    institutional_retail_gap: null,
    event_sensitivity: null,
    source_breakdown: { eodhd_news: 220, x_social: 80 },
    narrative: null,
    ...override,
  };
}

describe("EvidenceTab", () => {
  it("prompts for ticker when none selected", () => {
    render(<EvidenceTab selected={null} history={[]} />);
    expect(screen.getByText(/Select a single ticker/i)).toBeInTheDocument();
  });

  it("renders empty state when history is empty", () => {
    render(<EvidenceTab selected="AAPL" history={[]} />);
    expect(screen.getByTestId("evidence-empty")).toBeInTheDocument();
  });

  it("renders source filter pills, source cards, walkthrough, and feed", () => {
    render(<EvidenceTab selected="AAPL" history={[makeSnap()]} />);
    expect(screen.getByTestId("evidence-filter-all")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-filter-news")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-filter-social")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-source-eodhd_news")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-source-x_social")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-walkthrough")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-decomposition")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-feed")).toBeInTheDocument();
  });

  it("filters source cards by news / social pill", () => {
    render(<EvidenceTab selected="AAPL" history={[makeSnap()]} />);
    fireEvent.click(screen.getByTestId("evidence-filter-news"));
    expect(screen.getByTestId("evidence-source-eodhd_news")).toBeInTheDocument();
    expect(
      screen.queryByTestId("evidence-source-x_social"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("evidence-filter-social"));
    expect(
      screen.queryByTestId("evidence-source-eodhd_news"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("evidence-source-x_social")).toBeInTheDocument();
  });

  it("shows the no-sources state when source_breakdown is empty", () => {
    render(
      <EvidenceTab
        selected="AAPL"
        history={[makeSnap({ source_breakdown: {} })]}
      />,
    );
    expect(screen.getByTestId("evidence-no-sources")).toBeInTheDocument();
  });

  it("includes a Final composite row in the walkthrough", () => {
    render(<EvidenceTab selected="AAPL" history={[makeSnap()]} />);
    expect(screen.getByText(/= Final composite/i)).toBeInTheDocument();
  });
});
