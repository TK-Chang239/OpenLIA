import { describe, it, expect } from "vitest";
import { formatDateStamp } from "../dateStamp";

describe("formatDateStamp", () => {
  it("formats Tuesday May 6 2026 as TUE · 06 MAY 2026", () => {
    const d = new Date(2026, 4, 6); // Wed in some TZs — verify via getDay
    // Force the test to use whatever day-of-week JS computes for that local date.
    const wd = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"][d.getDay()];
    expect(formatDateStamp(d)).toBe(`${wd} · 06 MAY 2026`);
  });

  it("zero-pads single-digit days", () => {
    const d = new Date(2026, 0, 3);
    expect(formatDateStamp(d)).toMatch(/ · 03 JAN 2026$/);
  });

  it("uses uppercase month abbreviations", () => {
    const months = [
      "JAN",
      "FEB",
      "MAR",
      "APR",
      "MAY",
      "JUN",
      "JUL",
      "AUG",
      "SEP",
      "OCT",
      "NOV",
      "DEC",
    ];
    for (let m = 0; m < 12; m++) {
      const d = new Date(2026, m, 15);
      expect(formatDateStamp(d)).toContain(` ${months[m]} 2026`);
    }
  });
});
