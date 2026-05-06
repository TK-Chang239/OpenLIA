import { describe, it, expect } from "vitest";
import { mapToolCallToSource } from "../toolCallSourceMap";

describe("mapToolCallToSource", () => {
  it("maps read_repo_item to the filename + doc/pdf icon", () => {
    expect(
      mapToolCallToSource("read_repo_item", "filename=NVDA_10Q.pdf", null),
    ).toEqual({ label: "NVDA_10Q.pdf", kind: "pdf" });
    expect(
      mapToolCallToSource("read_repo_item", "", { filename: "notes.md" }),
    ).toEqual({ label: "notes.md", kind: "doc" });
  });

  it("maps news tools to the headline + news icon", () => {
    expect(
      mapToolCallToSource("search_news", "", { headline: "Apple beats Q3" }),
    ).toEqual({ label: "Apple beats Q3", kind: "news" });
  });

  it("maps generic search calls to a Search: prefix", () => {
    expect(
      mapToolCallToSource("web_search", "", { query: "rate cuts 2026" }),
    ).toEqual({ label: "Search: rate cuts 2026", kind: "search" });
  });

  it("maps quote/price tools to Market data + ticker", () => {
    expect(mapToolCallToSource("get_quote", "", { ticker: "NVDA" })).toEqual({
      label: "Market data — NVDA",
      kind: "data",
    });
  });

  it("falls back to tool_name(arg) for unknown tools", () => {
    expect(mapToolCallToSource("custom_tool", "x=1", null)).toEqual({
      label: "custom_tool(x=1)",
      kind: "search",
    });
  });

  it("maps consensus tool with analyst count", () => {
    expect(
      mapToolCallToSource("get_consensus", "", { count: 38 }),
    ).toEqual({ label: "Consensus — 38 analysts", kind: "data" });
  });
});
