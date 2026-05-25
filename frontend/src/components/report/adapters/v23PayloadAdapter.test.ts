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

describe("adaptV23PayloadToSchema — chart_type=table", () => {
  // The LLM picks chart_type='table' for peer-comp / key-metric panels
  // (per the SYNTHESIZE prompt's picking guidance). Before this fix the
  // adapter emitted a chart-shaped block tagged type='table' (with
  // `categories` + `series` instead of `headers` + `rows`), and the
  // frontend's TableBlock crashed on `headers.map(...)` because headers
  // was undefined. This suite locks in the conversion to a proper
  // TableBlock shape mirroring the docx native-table layout.

  function payloadWithTableChart(): V23RunPayload {
    const p = basePayload();
    p.bundle_facts = {
      ev_ebitda_a: { id: "ev_ebitda_a", label: "EV/EBITDA A", value: 14.2, unit: "x", ticker: "PEER_A" },
      ev_ebitda_b: { id: "ev_ebitda_b", label: "EV/EBITDA B", value: 11.8, unit: "x", ticker: "PEER_B" },
      pe_a: { id: "pe_a", label: "P/E A", value: 28.0, unit: "x", ticker: "PEER_A" },
      pe_b: { id: "pe_b", label: "P/E B", value: 22.5, unit: "x", ticker: "PEER_B" },
    };
    p.charts = [
      {
        id: "chart_peer_comp",
        section_id: "overview",
        claim: "Subject trades at a premium vs peers.",
        chart_type: "table",
        title: "Peer multiples",
        category_labels: ["Peer A", "Peer B"],
        series: [
          { name: "EV/EBITDA", value_fact_ids: ["ev_ebitda_a", "ev_ebitda_b"] },
          { name: "P/E", value_fact_ids: ["pe_a", "pe_b"] },
        ],
        x_axis_label: null,
        y_axis_label: null,
      },
    ];
    return p;
  }

  function findTableBlock(payload: V23RunPayload) {
    const schema = adaptV23PayloadToSchema(payload);
    const section = schema.sections.find((s) => s.id === "overview")!;
    const block = section.blocks.find((b) => (b as { type: string }).type === "table");
    return block as unknown as {
      type: "table";
      title: string;
      headers: { key: string; label: string }[];
      rows: Record<string, unknown>[];
    } | undefined;
  }

  it("converts a chart_type=table spec into a TableBlock with headers + rows", () => {
    const block = findTableBlock(payloadWithTableChart());
    expect(block).toBeDefined();
    expect(block!.type).toBe("table");
    expect(block!.title).toBe("Peer multiples");
    // Header layout: first column = category axis, then one column per series.
    expect(block!.headers).toHaveLength(3);
    expect(block!.headers[0].label).toBe("Category"); // no x_axis_label supplied
    expect(block!.headers[1].label).toBe("EV/EBITDA");
    expect(block!.headers[2].label).toBe("P/E");
    // Each header carries a unique key the rows are addressable by.
    const keys = block!.headers.map((h) => h.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("emits one row per category_label with cell values resolved from bundle_facts", () => {
    const block = findTableBlock(payloadWithTableChart())!;
    expect(block.rows).toHaveLength(2);
    const [headerCat, headerEvEbitda, headerPe] = block.headers;
    expect(block.rows[0][headerCat.key]).toBe("Peer A");
    expect(block.rows[0][headerEvEbitda.key]).toBe(14.2);
    expect(block.rows[0][headerPe.key]).toBe(28.0);
    expect(block.rows[1][headerCat.key]).toBe("Peer B");
    expect(block.rows[1][headerEvEbitda.key]).toBe(11.8);
    expect(block.rows[1][headerPe.key]).toBe(22.5);
  });

  it("uses x_axis_label as the first header label when supplied", () => {
    const payload = payloadWithTableChart();
    payload.charts[0].x_axis_label = "Peer";
    const block = findTableBlock(payload)!;
    expect(block.headers[0].label).toBe("Peer");
  });

  it("leaves the cell blank when a series fact_id is missing from bundle_facts", () => {
    const payload = payloadWithTableChart();
    delete payload.bundle_facts.ev_ebitda_b;
    const block = findTableBlock(payload)!;
    const evEbitdaKey = block.headers[1].key;
    expect(block.rows[0][evEbitdaKey]).toBe(14.2);
    expect(block.rows[1][evEbitdaKey]).toBe("");
  });

  it("does not crash TableBlock by leaving headers/rows undefined", () => {
    // Regression for the original crash: undefined headers → headers.map throws.
    const block = findTableBlock(payloadWithTableChart())!;
    expect(Array.isArray(block.headers)).toBe(true);
    expect(Array.isArray(block.rows)).toBe(true);
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
