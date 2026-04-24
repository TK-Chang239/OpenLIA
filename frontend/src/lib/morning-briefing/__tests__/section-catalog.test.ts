import { describe, expect, it } from "vitest";

import { DEFAULT_MB_SECTIONS, MB_SECTION_CATALOG } from "../section-catalog";

describe("MB section catalog", () => {
  it("exposes 7 default sections", () => {
    expect(DEFAULT_MB_SECTIONS.length).toBe(7);
  });

  it("has catalog entries for every default id", () => {
    for (const id of DEFAULT_MB_SECTIONS) {
      const entry = MB_SECTION_CATALOG[id];
      expect(entry).toBeDefined();
      expect(entry.title.length).toBeGreaterThan(0);
    }
  });

  it("catalog ids match framework JSON order", () => {
    expect(DEFAULT_MB_SECTIONS).toEqual([
      "executive_summary",
      "global_macro",
      "country_news",
      "market_news",
      "sector_news",
      "stock_news",
      "upcoming_preview",
    ]);
  });

  it("Executive Summary has no topic-input hint (toggle only)", () => {
    expect(MB_SECTION_CATALOG.executive_summary.hasTopics).toBe(false);
  });

  it("Upcoming Preview exposes reference-portfolio toggle", () => {
    expect(
      MB_SECTION_CATALOG.upcoming_preview.hasReferencePortfolioToggle,
    ).toBe(true);
  });
});
