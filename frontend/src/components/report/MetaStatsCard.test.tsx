import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MetaStats } from "../../api/reports";
import { MetaStatsCard } from "./MetaStatsCard";

function baseStats(): MetaStats {
  return {
    sections_count: 6,
    sources_count: 12,
    est_read_minutes: 5,
    web_search_queries: null,
    tokens_used: null,
    model_id: null,
  };
}

describe("MetaStatsCard — lane coverage rows", () => {
  it("does not render any coverage row when no lane fields are set", () => {
    render(<MetaStatsCard stats={baseStats()} />);
    expect(screen.queryByText(/data coverage/i)).toBeNull();
    expect(screen.queryByText(/web coverage/i)).toBeNull();
    expect(screen.queryByText(/narrative coverage/i)).toBeNull();
  });

  it("renders both Data coverage and Web coverage when the lane fields are present", () => {
    render(
      <MetaStatsCard
        stats={{
          ...baseStats(),
          data_coverage_label: "5/5",
          data_coverage_pct: 1,
          web_coverage_label: "3/4",
          web_coverage_pct: 0.75,
        }}
      />,
    );
    expect(screen.getByText("Data coverage")).toBeTruthy();
    expect(screen.getByText("5/5 (100%)")).toBeTruthy();
    expect(screen.getByText("Web coverage")).toBeTruthy();
    expect(screen.getByText("3/4 (75%)")).toBeTruthy();
    // The legacy chip is suppressed when the new lane fields are present —
    // otherwise the reader sees two rows that describe the same lane.
    expect(screen.queryByText("Narrative coverage")).toBeNull();
  });

  it("renders only the populated lane when the other is N/A", () => {
    render(
      <MetaStatsCard
        stats={{
          ...baseStats(),
          web_coverage_label: "0/4",
          web_coverage_pct: 0,
        }}
      />,
    );
    expect(screen.getByText("Web coverage")).toBeTruthy();
    expect(screen.getByText("0/4 (0%)")).toBeTruthy();
    expect(screen.queryByText("Data coverage")).toBeNull();
  });
});

describe("MetaStatsCard — legacy narrative_coverage back-compat", () => {
  it("renders the legacy chip when only the deprecated fields are present", () => {
    render(
      <MetaStatsCard
        stats={{
          ...baseStats(),
          narrative_coverage_label: "3/4",
          narrative_coverage_pct: 0.75,
        }}
      />,
    );
    expect(screen.getByText("Narrative coverage")).toBeTruthy();
    expect(screen.getByText("3/4 (75%)")).toBeTruthy();
  });
});
