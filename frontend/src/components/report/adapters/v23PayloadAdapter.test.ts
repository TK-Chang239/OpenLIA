import { describe, expect, it } from "vitest";

import type { V23RunPayload } from "../../../api/equity-research-v2-3";
import { adaptV23PayloadToSchema } from "./v23PayloadAdapter";

function basePayload(): V23RunPayload {
  return {
    run_id: "r1",
    tickers: ["NVDA"],
    report_type: "initiation",
    language: "en",
    thesis: {
      language: "en",
      central_argument: "Long thesis intact.",
      key_takeaways: ["Takeaway one.", "Takeaway two.", "Takeaway three."],
      valuation_stance: "Buy with 22% upside to target.",
      canonical_figures: [
        { fact_id: "rev_ttm", display: "$60.9B" },
        { fact_id: "gross_margin_ttm", display: "74.2%" },
      ],
    },
    sections: [
      { id: "overview", title: "Business Overview" },
      { id: "risks", title: "Risks" },
    ],
    section_bodies: {
      overview: "Body of the overview section.",
      risks: "Body of the risks section.",
    },
    footnotes: ["EODHD (fundamentals), latest."],
    charts: [],
    figure_labels: {},
    bundle_facts: {
      rev_ttm: { id: "rev_ttm", label: "Revenue (TTM)", value: 60_900_000_000, unit: "USD", ticker: "NVDA" },
      gross_margin_ttm: { id: "gross_margin_ttm", label: "Gross margin (TTM)", value: 0.742, unit: "percent", ticker: "NVDA" },
    },
    narrative_coverage: null,
  };
}

describe("adaptV23PayloadToSchema — duplication regression", () => {
  it("does not prepend metric_cards / key_finding / rating_badge to the first section", () => {
    const schema = adaptV23PayloadToSchema(basePayload());
    const firstSection = schema.sections[0];
    const blockTypes = firstSection.blocks.map((b) => (b as { type: string }).type);
    expect(blockTypes).not.toContain("metric_cards");
    expect(blockTypes).not.toContain("key_finding");
    expect(blockTypes).not.toContain("rating_badge");
  });

  it("still surfaces the headline view on the cover (tldr + key_metrics + consensus_rating)", () => {
    const schema = adaptV23PayloadToSchema(basePayload());
    expect(schema.cover.tldr).toEqual(["Takeaway one.", "Takeaway two.", "Takeaway three."]);
    expect(schema.cover.tldr_label).toBe("Key takeaways");
    expect(schema.cover.key_metrics).toHaveLength(2);
    expect(schema.cover.key_metrics?.[0].label).toBe("Revenue (TTM)");
    expect(schema.cover.consensus_rating).toBe("Buy");
  });

  it("renders each section as text-only when the body has prose", () => {
    const schema = adaptV23PayloadToSchema(basePayload());
    for (const section of schema.sections) {
      const types = section.blocks.map((b) => (b as { type: string }).type);
      expect(types).toEqual(["text"]);
    }
  });
});

describe("adaptV23PayloadToSchema — narrative coverage signal", () => {
  it("leaves the narrative_coverage_* meta_stats fields null when the payload omits the signal", () => {
    const schema = adaptV23PayloadToSchema(basePayload());
    expect(schema.meta_stats?.narrative_coverage_label).toBeNull();
    expect(schema.meta_stats?.narrative_coverage_pct).toBeNull();
  });

  it("surfaces the signal as 'satisfied/total' + pct when present", () => {
    const payload = basePayload();
    payload.narrative_coverage = { total: 4, satisfied: 3, pct: 0.75 };
    const schema = adaptV23PayloadToSchema(payload);
    expect(schema.meta_stats?.narrative_coverage_label).toBe("3/4");
    expect(schema.meta_stats?.narrative_coverage_pct).toBe(0.75);
  });

  it("surfaces 0/N when no narrative needs were satisfied", () => {
    const payload = basePayload();
    payload.narrative_coverage = { total: 4, satisfied: 0, pct: 0 };
    const schema = adaptV23PayloadToSchema(payload);
    expect(schema.meta_stats?.narrative_coverage_label).toBe("0/4");
    expect(schema.meta_stats?.narrative_coverage_pct).toBe(0);
  });
});
