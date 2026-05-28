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
      display_index: null,
      provenance: {},
    },
  ],
};

function makeDetail(overrides: Partial<V3ReportDetail> = {}): V3ReportDetail {
  return {
    ...DETAIL,
    sections: [],
    charts: [],
    citations: [],
    ...overrides,
  };
}

describe("adaptV3DetailToSchema — citations + cover", () => {
  test("rewrites [^source_id] markers to [N] using display_index", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const overview = schema.sections[0];
    const text = (overview.blocks[0] as { type: "text"; content: string })
      .content;
    expect(text).toContain("[1]");
    expect(text).not.toContain("[^web_1]");
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

describe("adaptV3DetailToSchema — inline chart placement", () => {
  test("splits prose around a {{chart:id}} marker into text → chart → text", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const model = schema.sections[1];
    expect(model.blocks.length).toBe(3);
    expect(model.blocks[0].type).toBe("text");
    expect(
      (model.blocks[0] as { content: string }).content,
    ).toContain("Annual revenue trajectory");
    expect(model.blocks[1].type).toBe("bar_chart");
    expect(model.blocks[2].type).toBe("text");
    // [^eodhd_1] rewrites to [2] in the trailing prose
    expect(
      (model.blocks[2] as { content: string }).content,
    ).toContain("[2]");
  });

  test("renders multiple charts in one section in marker order", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "A {{chart:a}} B {{chart:b}} C",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "a",
          chart_type: "bar",
          title: "Chart A",
          spec: { data: [{ label: "x", value: 1 }] },
          rendered_url: null,
          version: 1,
        },
        {
          chart_id: "b",
          chart_type: "line",
          title: "Chart B",
          spec: { data: [{ label: "y", value: 2 }] },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const types = adaptV3DetailToSchema(detail).sections[0].blocks.map(
      (b) => b.type,
    );
    expect(types).toEqual([
      "text",
      "bar_chart",
      "text",
      "line_chart",
      "text",
    ]);
  });

  test("repeated marker for the same chart only renders the chart once", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "First mention {{chart:x}} and again {{chart:x}} end.",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "x",
          chart_type: "bar",
          title: "X",
          spec: { data: [{ label: "a", value: 1 }] },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const blocks = adaptV3DetailToSchema(detail).sections[0].blocks;
    expect(blocks.filter((b) => b.type === "bar_chart").length).toBe(1);
  });

  test('unreferenced charts land in a trailing "Additional charts" section', () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const extras = schema.sections.find((s) => s.id === "__v3_extra_charts__");
    expect(extras).toBeDefined();
    expect(extras?.title).toBe("Additional charts");
    expect(extras?.blocks).toHaveLength(1);
  });

  test("text-only sections (no chart marker) still get one TextBlock", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "Just text with a citation [^web_1].",
          version: 1,
        },
      ],
      citations: [
        {
          source_id: "web_1",
          tool_name: "web_search",
          display_index: 1,
          provenance: { url: "https://example.com" },
        },
      ],
    });
    const blocks = adaptV3DetailToSchema(detail).sections[0].blocks;
    expect(blocks.length).toBe(1);
    expect(blocks[0].type).toBe("text");
    expect((blocks[0] as { content: string }).content).toContain("[1]");
  });
});

describe("adaptV3DetailToSchema — chart shape mapping", () => {
  test("bar chart maps categorical {label, value} data to v1 categories + series", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    const chartBlock = schema.sections[1].blocks.find(
      (b) => b.type === "bar_chart",
    ) as Record<string, unknown> | undefined;
    expect(chartBlock).toBeDefined();
    expect(chartBlock?.title).toBe("Revenue trend");
    expect(chartBlock?.categories).toEqual(["2024", "2025", "2026"]);
    const series = chartBlock?.series as Array<{
      name: string;
      values: number[];
    }>;
    expect(series).toHaveLength(1);
    expect(series[0].name).toBe("Revenue ($M)");
    expect(series[0].values).toEqual([436, 575, 740]);
  });

  test("pie chart emits segments, not categories/series", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:p}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "p",
          chart_type: "pie",
          title: "Pie",
          spec: {
            data: [
              { label: "A", value: 60 },
              { label: "B", value: 40 },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const blocks = adaptV3DetailToSchema(detail).sections[0].blocks;
    const pie = blocks.find((b) => b.type === "pie_chart") as {
      type: string;
      segments: Array<{ label: string; value: number }>;
    };
    expect(pie).toBeDefined();
    expect(pie.segments).toEqual([
      { label: "A", value: 60 },
      { label: "B", value: 40 },
    ]);
  });

  test("scatter chart emits series[].data of {x, y} objects", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:sc}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "sc",
          chart_type: "scatter",
          title: "Scatter",
          spec: {
            data: [
              { x: 1, y: 2 },
              { x: 3, y: 4 },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const blocks = adaptV3DetailToSchema(detail).sections[0].blocks;
    const scatter = blocks.find((b) => b.type === "scatter_plot") as {
      type: string;
      series: Array<{ name: string; data: Array<{ x: number; y: number }> }>;
    };
    expect(scatter).toBeDefined();
    expect(scatter.series[0].data).toEqual([
      { x: 1, y: 2 },
      { x: 3, y: 4 },
    ]);
  });

  test("table chart maps spec.data rows to TableBlock headers + rows", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:t}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "t",
          chart_type: "table",
          title: "Comp Table",
          spec: {
            data: [
              { metric: "Revenue", value: "$1B" },
              { metric: "Growth", value: "20%" },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const blocks = adaptV3DetailToSchema(detail).sections[0].blocks;
    const table = blocks.find((b) => b.type === "table") as {
      type: string;
      headers: Array<{ key: string; label: string }>;
      rows: Array<Record<string, unknown>>;
    };
    expect(table.headers.map((h) => h.key)).toEqual(["metric", "value"]);
    expect(table.rows.length).toBe(2);
  });

  test("unrecognised chart_type emits a TextBlock placeholder", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:w}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "w",
          chart_type: "waterfall",
          title: "Waterfall",
          spec: { data: [{ label: "x", value: 1 }] },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const blocks = adaptV3DetailToSchema(detail).sections[0].blocks;
    const block = blocks.find(
      (b) => b.type === "text" && "content" in b,
    ) as { content: string };
    expect(block.content).toContain("Waterfall");
    expect(block.content).toContain("waterfall");
  });
});
