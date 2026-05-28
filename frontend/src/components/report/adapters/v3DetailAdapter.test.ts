import { describe, expect, test } from "vitest";

import type { V3ReportDetail } from "../../../api/equity-research-v3";
import { adaptV3DetailToSchema } from "./v3DetailAdapter";

const DETAIL: V3ReportDetail = {
  report: {
    report_id: "rpt-1",
    subject: "RKLB.US",
    template_id: "initiation_default",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: "2026-05-27T10:00:00Z",
    completed_at: "2026-05-27T10:05:00Z",
  },
  error_message: null,
  sections: [
    {
      section_id: "overview",
      section_index: 0,
      title: "Overview",
      markdown: "Rocket Lab is a launch provider [^web_1].",
      version: 1,
    },
    {
      section_id: "model",
      section_index: 1,
      title: "Model",
      markdown:
        "Annual revenue trajectory:\n\n{{chart:rev_trend}}\n\nGrowth driven by Neutron [^eodhd_1].",
      version: 2,
    },
  ],
  charts: [
    {
      chart_id: "rev_trend",
      chart_type: "bar",
      title: "Revenue trend",
      spec: {
        chart_id: "rev_trend",
        chart_type: "bar",
        title: "Revenue trend",
        data: [
          { label: "2024", value: 436 },
          { label: "2025", value: 575 },
          { label: "2026", value: 740 },
        ],
        axes: { x: "Fiscal year", y: "Revenue ($M)" },
      },
      rendered_url: null,
      version: 1,
    },
    {
      chart_id: "orphan",
      chart_type: "line",
      title: "Unreferenced",
      spec: {
        chart_id: "orphan",
        chart_type: "line",
        title: "Unreferenced",
        data: [{ x: 1, y: 2 }],
      },
      rendered_url: null,
      version: 1,
    },
  ],
  citations: [
    {
      source_id: "web_1",
      tool_name: "web_search",
      display_index: 1,
      provenance: { url: "https://example.com/rklb" },
    },
    {
      source_id: "eodhd_1",
      tool_name: "get_company_news",
      display_index: 2,
      provenance: { ticker: "RKLB" },
    },
    {
      source_id: "web_2",
      tool_name: "web_search",
      display_index: null, // not referenced from sections
      provenance: {},
    },
  ],
};

describe("adaptV3DetailToSchema", () => {
  test("rewrites [^source_id] markers to [N] using display_index", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const overview = schema.sections[0];
    const text = (overview.blocks[0] as { type: "text"; content: string }).content;
    expect(text).toContain("[1]");
    expect(text).not.toContain("[^web_1]");
  });

  test("strips {{chart:id}} placeholders from prose and emits chart block in the same section", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const model = schema.sections[1];
    const text = (model.blocks[0] as { type: "text"; content: string }).content;
    expect(text).not.toContain("{{chart:rev_trend}}");
    const blockTypes = model.blocks.map((b) => b.type);
    expect(blockTypes).toContain("bar_chart");
    // [^eodhd_1] rewrites to [2]
    expect(text).toContain("[2]");
  });

  test("bar chart maps categorical {label, value} data to v1 categories + series", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const chartBlock = schema.sections[1].blocks.find(
      (b) => b.type === "bar_chart",
    ) as Record<string, unknown> | undefined;
    expect(chartBlock).toBeDefined();
    expect(chartBlock?.title).toBe("Revenue trend");
    expect(chartBlock?.categories).toEqual(["2024", "2025", "2026"]);
    const series = chartBlock?.series as Array<{ name: string; values: number[] }>;
    expect(series).toHaveLength(1);
    expect(series[0].name).toBe("Revenue ($M)");
    expect(series[0].values).toEqual([436, 575, 740]);
  });

  test('unreferenced charts land in a trailing "Additional charts" section', () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const extras = schema.sections.find((s) => s.id === "__v3_extra_charts__");
    expect(extras).toBeDefined();
    expect(extras?.title).toBe("Additional charts");
    expect(extras?.blocks).toHaveLength(1);
  });

  test("citations adapt to v1 shape (id = display_index, URL from provenance)", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const citations = schema.citations ?? [];
    expect(citations).toHaveLength(2);
    expect(citations[0].id).toBe("1");
    expect(citations[0].url).toBe("https://example.com/rklb");
    expect(citations[1].id).toBe("2");
    expect(citations[1].source).toBe("get_company_news");
  });

  test("cover surfaces subject + template-derived eyebrow", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    expect(schema.cover.title).toBe("RKLB.US");
    expect(schema.cover.eyebrow).toBe("Stock Initiation Report");
    expect(schema.cover.ticker).toBe("RKLB.US");
  });
});
