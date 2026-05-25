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

describe("MetaStatsCard — narrative coverage row", () => {
  it("does not render the row when the label is absent", () => {
    render(<MetaStatsCard stats={baseStats()} />);
    expect(screen.queryByText(/narrative coverage/i)).toBeNull();
  });

  it("renders the row as 'satisfied/total (NN%)' when present", () => {
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

  it("renders 0/N with 0% when nothing was satisfied", () => {
    render(
      <MetaStatsCard
        stats={{
          ...baseStats(),
          narrative_coverage_label: "0/4",
          narrative_coverage_pct: 0,
        }}
      />,
    );
    expect(screen.getByText("0/4 (0%)")).toBeTruthy();
  });
});
