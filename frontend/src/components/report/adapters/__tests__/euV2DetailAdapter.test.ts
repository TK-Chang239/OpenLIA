import { describe, expect, it } from "vitest";
import { adaptEuV2DetailToSchema } from "../euV2DetailAdapter";
import type { RunDetail } from "../../../../api/earnings-update";

const detail: RunDetail = {
  report: {
    report_id: "r1",
    ticker: "MSFT.US",
    subject: "MSFT.US Q3 FY26 earnings",
    template_id: "eu_default",
    status: "completed",
    trigger_kind: "on_demand",
    fiscal_date: null,
    language: "en",
    length: "normal",
    created_at: "2026-05-30T00:00:00Z",
    completed_at: null,
    reasoning_effort: null,
  },
  error_message: null,
  sections: [
    {
      section_id: "quick_take",
      section_index: 0,
      title: "Quick Take",
      markdown: "Beat on EPS [^eodhd_1].",
      version: 1,
    },
  ],
  charts: [],
  citations: [
    {
      source_id: "eodhd_1",
      tool_name: "get_fundamentals",
      display_index: 1,
      provenance: { url: "https://eodhd.com" },
    },
  ],
  cover: { subtitle: "Q3 FY26", tldr: ["Strong quarter"], rating: "Buy" },
};

describe("adaptEuV2DetailToSchema", () => {
  it("produces a ReportSchema with the section and a resolved citation", () => {
    const schema = adaptEuV2DetailToSchema(detail);
    expect(schema.sections.length).toBe(1);
    expect(schema.citations?.length).toBe(1);
    // citation marker [^eodhd_1] rewritten to a numeric index in the section text
    const text = JSON.stringify(schema.sections[0]);
    expect(text).not.toContain("[^eodhd_1]");
  });

  it("sets department to earnings_update", () => {
    const schema = adaptEuV2DetailToSchema(detail);
    expect(schema.department).toBe("earnings_update");
  });
});
