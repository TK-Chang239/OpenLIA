import React from "react";
import { describe, expect, test } from "vitest";
import { render } from "@testing-library/react";

import type { V3ReportDetail } from "../../../api/equity-research-v3";
import { LineChartBlock } from "../charts/LineChartBlock";
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

  test("cover falls back to empty subtitle / tagline / tldr / metrics when detail.cover is absent (PR9)", () => {
    const schema = adaptV3DetailToSchema(DETAIL);
    expect(schema.cover.subtitle).toBe("");
    expect(schema.cover.tagline).toBe("");
    expect(schema.cover.tldr).toEqual([]);
    expect(schema.cover.key_metrics).toEqual([]);
    expect(schema.cover.consensus_rating).toBeNull();
  });

  test("cover highlights rewrite [^source_id] markers like body sections do", () => {
    const detail = makeDetail({
      cover: {
        subtitle: "Initiation [^web_1]",
        tagline: "Leader in launch [^eodhd_2]",
        tldr: ["Backlog grew 40%.[^web_1]", "Cash burn narrowing.[^ghost_9]"],
        key_metrics: [],
        rating: null,
        upside_pct: null,
      },
      citations: [
        {
          source_id: "web_1",
          tool_name: "web_search",
          display_index: 1,
          provenance: {},
        },
        {
          source_id: "eodhd_2",
          tool_name: "get_fundamentals",
          display_index: 2,
          provenance: {},
        },
      ],
    });
    const schema = adaptV3DetailToSchema(detail);
    expect(schema.cover.subtitle).toBe("Initiation [1]");
    expect(schema.cover.tagline).toBe("Leader in launch [2]");
    expect(schema.cover.tldr).toEqual([
      "Backlog grew 40%.[1]",
      // Unknown ids lose the caret but keep the id visible.
      "Cash burn narrowing.[ghost_9]",
    ]);
  });

  test("cover populates subtitle / tagline / tldr / metrics / rating from detail.cover (PR9)", () => {
    const schema = adaptV3DetailToSchema({
      ...DETAIL,
      cover: {
        subtitle: "Q1 2026 initiation",
        tagline: "Pure-play orbital launch leader",
        tldr: ["Backlog at $1.2B", "Neutron on track", "Margin path to 35%"],
        key_metrics: [
          {
            label: "Revenue FY24",
            value: "$436M",
            change: "+24% YoY",
            tone: "positive",
          },
          { label: "Backlog", value: "$1.2B" },
        ],
        rating: "Buy",
        upside_pct: 28.5,
      },
    });
    expect(schema.cover.subtitle).toBe("Q1 2026 initiation");
    expect(schema.cover.tagline).toBe("Pure-play orbital launch leader");
    expect(schema.cover.tldr).toEqual([
      "Backlog at $1.2B",
      "Neutron on track",
      "Margin path to 35%",
    ]);
    expect(schema.cover.key_metrics).toHaveLength(2);
    expect(schema.cover.key_metrics?.[0]).toMatchObject({
      label: "Revenue FY24",
      value: "$436M",
      delta: "+24% YoY",
      delta_direction: "up",
      tag: { tone: "positive" },
    });
    expect(schema.cover.consensus_rating).toBe("Buy");
    expect(schema.cover.consensus_upside_pct).toBe(28.5);
  });

  test("cover metric tone maps to direction: positive=up, negative=down, neutral=flat (PR9)", () => {
    const schema = adaptV3DetailToSchema({
      ...DETAIL,
      cover: {
        tldr: [],
        key_metrics: [
          { label: "A", value: "1", tone: "positive" },
          { label: "B", value: "2", tone: "negative" },
          { label: "C", value: "3", tone: "neutral" },
          { label: "D", value: "4" },
        ],
      },
    });
    const directions = schema.cover.key_metrics?.map((m) => m.delta_direction);
    expect(directions).toEqual(["up", "down", "flat", null]);
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

  test("line chart groups points by series over shared deduplicated categories", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:ln}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "ln",
          chart_type: "line",
          title: "Revenue and FCF",
          spec: {
            data: [
              { x: "FY2024", y: 60.9, series: "Revenue" },
              { x: "FY2025", y: 130.5, series: "Revenue" },
              { x: "FY2026", y: 215.9, series: "Revenue" },
              { x: "FY2024", y: 27.0, series: "Free Cash Flow" },
              { x: "FY2025", y: 60.9, series: "Free Cash Flow" },
              { x: "FY2026", y: 96.7, series: "Free Cash Flow" },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const blocks = adaptV3DetailToSchema(detail).sections[0].blocks;
    const chartBlock = blocks.find((b) => b.type === "line_chart") as
      | Record<string, unknown>
      | undefined;
    expect(chartBlock).toBeDefined();
    expect(chartBlock?.categories).toEqual(["FY2024", "FY2025", "FY2026"]);
    const series = chartBlock?.series as Array<{ name: string; values: number[] }>;
    expect(series).toHaveLength(2);
    expect(series[0]).toEqual({ name: "Revenue", values: [60.9, 130.5, 215.9] });
    expect(series[1]).toEqual({ name: "Free Cash Flow", values: [27.0, 60.9, 96.7] });
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

  test("line chart drops NaN-producing points instead of poisoning the y-axis", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:l}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "l",
          chart_type: "line",
          title: "Mixed",
          spec: {
            data: [
              { label: "2024", value: 100 },
              { label: "2025", value: "n/a" }, // unparseable
              { label: "2026", value: 300 },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const block = adaptV3DetailToSchema(detail).sections[0].blocks.find(
      (b) => b.type === "line_chart",
    ) as unknown as { categories: string[]; series: Array<{ values: number[] }> };
    expect(block.categories).toEqual(["2024", "2026"]);
    expect(block.series[0].values).toEqual([100, 300]);
  });

  test("line chart coerces numeric strings with currency/scale suffixes", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:l}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "l",
          chart_type: "line",
          title: "Scaled",
          spec: {
            data: [
              { label: "Q1", value: "$1.2M" },
              { label: "Q2", value: "1,500" },
              { label: "Q3", value: "2B" },
              { label: "Q4", value: "50%" },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const block = adaptV3DetailToSchema(detail).sections[0].blocks.find(
      (b) => b.type === "line_chart",
    ) as unknown as { categories: string[]; series: Array<{ values: number[] }> };
    expect(block.categories).toEqual(["Q1", "Q2", "Q3", "Q4"]);
    expect(block.series[0].values).toEqual([
      1_200_000,
      1500,
      2_000_000_000,
      50,
    ]);
  });

  test("line chart accepts mixed {label,value} + {x,y} within one chart", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:l}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "l",
          chart_type: "line",
          title: "Mixed shapes",
          spec: {
            data: [
              { label: "Q1", value: 100 },
              { x: "Q2", y: 200 }, // model accidentally switched shape
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const block = adaptV3DetailToSchema(detail).sections[0].blocks.find(
      (b) => b.type === "line_chart",
    ) as unknown as { categories: string[]; series: Array<{ values: number[] }> };
    expect(block.categories).toEqual(["Q1", "Q2"]);
    expect(block.series[0].values).toEqual([100, 200]);
  });

  test("scatter drops points where x or y won't coerce", () => {
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
          title: "Sparse",
          spec: {
            data: [
              { x: 1, y: 10 },
              { x: "n/a", y: 20 },
              { x: 3, y: 30 },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const block = adaptV3DetailToSchema(detail).sections[0].blocks.find(
      (b) => b.type === "scatter_plot",
    ) as unknown as { series: Array<{ data: Array<{ x: number; y: number }> }> };
    expect(block.series[0].data).toEqual([
      { x: 1, y: 10 },
      { x: 3, y: 30 },
    ]);
  });

  test("pie chart drops zero-value segments (would render as invisible slices)", () => {
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
              { label: "B", value: 0 },
              { label: "C", value: 40 },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const pie = adaptV3DetailToSchema(detail).sections[0].blocks.find(
      (b) => b.type === "pie_chart",
    ) as unknown as { segments: Array<{ label: string; value: number }> };
    expect(pie.segments.map((s) => s.label)).toEqual(["A", "C"]);
  });

  test("chart with all-NaN values falls back to text placeholder", () => {
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:b}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "b",
          chart_type: "bar",
          title: "Broken",
          spec: {
            data: [
              { label: "x", value: "n/a" },
              { label: "y", value: "tbd" },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const block = adaptV3DetailToSchema(detail).sections[0].blocks[0] as {
      type: string;
      content?: string;
    };
    expect(block.type).toBe("text");
    expect(block.content).toContain("Broken");
  });

  test("e2e: LineChartBlock renders a polyline from adapter output (NaN-resilient)", () => {
    // Regression: before the per-point numeric coercion, a single
    // unparseable value (e.g. "n/a") produced a NaN in `values[]`,
    // which then propagated through Math.min/max and silently
    // collapsed the chart to a blank SVG.
    const detail = makeDetail({
      sections: [
        {
          section_id: "s",
          section_index: 0,
          title: "S",
          markdown: "{{chart:l}}",
          version: 1,
        },
      ],
      charts: [
        {
          chart_id: "l",
          chart_type: "line",
          title: "Revenue",
          spec: {
            data: [
              { label: "2024", value: "$436M" },
              { label: "2025", value: 575_000_000 },
              { label: "2026", value: "n/a" },
              { label: "2027", value: "1.2B" },
            ],
          },
          rendered_url: null,
          version: 1,
        },
      ],
    });
    const block = adaptV3DetailToSchema(detail).sections[0].blocks.find(
      (b) => b.type === "line_chart",
    );
    expect(block).toBeDefined();
    // The chart block ships shape that LineChartBlock can consume.
    const { container } = render(
      React.createElement(LineChartBlock, block as never),
    );
    // Polyline only renders when there are finite y-values.
    expect(container.querySelectorAll("polyline.series-line").length).toBe(1);
    // Three valid points survive ("2024", "2025", "2027").
    expect(container.querySelectorAll("circle.series-dot").length).toBe(3);
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
