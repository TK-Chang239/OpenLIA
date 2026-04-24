import { describe, expect, it } from "vitest";

import {
  DEFAULT_EU_SECTIONS,
  EU_SECTION_CATALOG,
} from "../section-catalog";

describe("EU section catalog", () => {
  it("exposes 8 default sections", () => {
    expect(DEFAULT_EU_SECTIONS.length).toBe(8);
  });

  it("has catalog entries for every default id", () => {
    for (const id of DEFAULT_EU_SECTIONS) {
      const entry = EU_SECTION_CATALOG[id];
      expect(entry).toBeDefined();
      expect(entry.title.length).toBeGreaterThan(0);
      expect(entry.description.length).toBeGreaterThan(0);
    }
  });

  it("catalog ids match the framework JSON", () => {
    const frameworkIds = [
      "quick_take",
      "market_reaction",
      "key_financials",
      "operational_highlights",
      "forward_guidance",
      "earnings_call",
      "risk_assessment",
      "thesis_check",
    ];
    expect([...DEFAULT_EU_SECTIONS]).toEqual(frameworkIds);
  });
});
