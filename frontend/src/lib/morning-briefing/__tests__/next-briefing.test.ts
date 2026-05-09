import { describe, expect, it } from "vitest";

import type { MbSchedule } from "../../../api/morning-briefing";
import {
  formatNextBriefing,
  pickEarliestNextBriefing,
} from "../next-briefing";

const baseSchedule: MbSchedule = {
  id: "s1",
  time: "07:00",
  timezone: "America/New_York",
  days_of_week: ["mon", "tue", "wed", "thu", "fri"],
  label: "Pre-market",
  is_enabled: true,
};

describe("formatNextBriefing", () => {
  it("returns em-dash when schedule is null", () => {
    expect(formatNextBriefing(null)).toBe("—");
  });

  it("returns em-dash when schedule is disabled", () => {
    expect(
      formatNextBriefing({ ...baseSchedule, is_enabled: false }),
    ).toBe("—");
  });

  it("returns em-dash when no days are selected", () => {
    expect(
      formatNextBriefing({ ...baseSchedule, days_of_week: [] }),
    ).toBe("—");
  });

  it("formats today when current time is before scheduled time on a scheduled day", () => {
    // Mon 2026-05-04 04:00 ET -> 08:00 UTC
    const now = new Date("2026-05-04T08:00:00Z");
    const out = formatNextBriefing(baseSchedule, now);
    expect(out.startsWith("Today")).toBe(true);
    expect(out).toMatch(/7:00 AM/);
  });

  it("rolls to tomorrow when today's time has already passed", () => {
    // Mon 2026-05-04 12:00 ET -> 16:00 UTC; next is Tue
    const now = new Date("2026-05-04T16:00:00Z");
    const out = formatNextBriefing(baseSchedule, now);
    expect(out.startsWith("Tomorrow")).toBe(true);
    expect(out).toMatch(/7:00 AM/);
  });

  it("skips weekend when schedule is weekdays-only", () => {
    // Sat 2026-05-09 12:00 UTC; expect Mon 2026-05-11
    const now = new Date("2026-05-09T12:00:00Z");
    const out = formatNextBriefing(baseSchedule, now);
    expect(out.startsWith("Mon")).toBe(true);
  });
});

describe("pickEarliestNextBriefing", () => {
  it("returns null when no schedules", () => {
    expect(pickEarliestNextBriefing([])).toBeNull();
    expect(pickEarliestNextBriefing(null)).toBeNull();
  });

  it("picks the earliest upcoming run across multiple schedules", () => {
    // Mon 2026-05-04 04:00 ET (08:00 UTC).
    const now = new Date("2026-05-04T08:00:00Z");
    const morning: MbSchedule = { ...baseSchedule, id: "a", time: "07:00" };
    const evening: MbSchedule = {
      ...baseSchedule,
      id: "b",
      time: "16:30",
      label: "Post-Market",
    };
    const out = pickEarliestNextBriefing([evening, morning], now);
    expect(out?.schedule.id).toBe("a");
    expect(out?.display).toMatch(/7:00 AM/);
  });

  it("ignores disabled schedules", () => {
    const now = new Date("2026-05-04T08:00:00Z");
    const morning: MbSchedule = {
      ...baseSchedule,
      id: "a",
      time: "07:00",
      is_enabled: false,
    };
    const evening: MbSchedule = {
      ...baseSchedule,
      id: "b",
      time: "16:30",
    };
    const out = pickEarliestNextBriefing([morning, evening], now);
    expect(out?.schedule.id).toBe("b");
  });
});
