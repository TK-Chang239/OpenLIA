import { describe, it, expect } from "vitest";
import {
  SUGGESTION_BANK,
  pickSuggestions,
  type SuggestionDept,
} from "../suggestionsBank";

const DEPTS: SuggestionDept[] = [
  "earnings_update",
  "macro_research",
  "portfolio",
  "retail_sentiment",
];

describe("pickSuggestions", () => {
  it("returns 4 entries — one per dept slot — in order", () => {
    const out = pickSuggestions(SUGGESTION_BANK, "seed-a");
    expect(out).toHaveLength(4);
    expect(out.map((s) => s.dept)).toEqual(DEPTS);
  });

  it("is deterministic per seed", () => {
    const a = pickSuggestions(SUGGESTION_BANK, "seed-x");
    const b = pickSuggestions(SUGGESTION_BANK, "seed-x");
    expect(a).toEqual(b);
  });

  it("a different seed yields a different selection (at least one slot)", () => {
    const a = pickSuggestions(SUGGESTION_BANK, "2026-05-06#0");
    const b = pickSuggestions(SUGGESTION_BANK, "2026-05-06#1");
    const same = a.every((sa, i) => sa.question === b[i].question);
    expect(same).toBe(false);
  });

  it("every slot's pick belongs to that dept's candidate pool", () => {
    const out = pickSuggestions(SUGGESTION_BANK, "seed-z");
    for (const s of out) {
      expect(SUGGESTION_BANK.filter((b) => b.dept === s.dept)).toContain(s);
    }
  });
});
