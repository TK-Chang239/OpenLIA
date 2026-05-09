import { describe, it, expect } from "vitest";
import {
  GREETING_BANK,
  pickGreeting,
  localDaySeed,
  timeOfDayGreeting,
} from "../greetings";

describe("pickGreeting", () => {
  it("returns the same phrase for the same seed", () => {
    const a = pickGreeting(GREETING_BANK, "2026-05-06");
    const b = pickGreeting(GREETING_BANK, "2026-05-06");
    expect(a).toEqual(b);
  });

  it("rotates with a different seed", () => {
    const seeds = ["2026-05-06", "2026-05-07", "2026-05-08", "2026-05-09"];
    const picks = new Set(
      seeds.map((s) => pickGreeting(GREETING_BANK, s).accent),
    );
    expect(picks.size).toBeGreaterThanOrEqual(2);
  });

  it("always picks something inside the bank", () => {
    const out = pickGreeting(GREETING_BANK, "any-seed-here");
    expect(GREETING_BANK).toContain(out);
  });

  it("throws on an empty bank", () => {
    expect(() => pickGreeting([], "x")).toThrow();
  });
});

describe("localDaySeed", () => {
  it("formats the date as YYYY-MM-DD", () => {
    const d = new Date(2026, 4, 6); // 2026-05-06 (month is 0-indexed)
    expect(localDaySeed(d)).toBe("2026-05-06");
  });

  it("zero-pads month and day", () => {
    const d = new Date(2026, 0, 3);
    expect(localDaySeed(d)).toBe("2026-01-03");
  });
});

describe("timeOfDayGreeting", () => {
  it("morning before noon", () => {
    const d = new Date(2026, 4, 6, 8, 0, 0);
    expect(timeOfDayGreeting(d)).toBe("Good morning");
  });

  it("afternoon between noon and 6pm", () => {
    const d = new Date(2026, 4, 6, 14, 0, 0);
    expect(timeOfDayGreeting(d)).toBe("Good afternoon");
  });

  it("evening at and after 6pm", () => {
    const d = new Date(2026, 4, 6, 19, 0, 0);
    expect(timeOfDayGreeting(d)).toBe("Good evening");
  });
});
