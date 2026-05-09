import type { MbSchedule } from "../../api/morning-briefing";

const DAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;

export interface NextOccurrence {
  schedule: MbSchedule;
  at: Date;
  display: string;
}

function partsInTz(date: Date, timeZone: string) {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZoneName: "short",
  });
  const parts = Object.fromEntries(
    fmt.formatToParts(date).map((p) => [p.type, p.value]),
  );
  const weekday = (parts.weekday ?? "").toLowerCase().slice(0, 3);
  const hour = Number(parts.hour ?? "0");
  const minute = Number(parts.minute ?? "0");
  const tzName = parts.timeZoneName ?? timeZone;
  return { weekday, hour, minute, tzName };
}

function formatTime12(hh: number, mm: number): string {
  const period = hh >= 12 ? "PM" : "AM";
  const h = hh === 0 ? 12 : hh > 12 ? hh - 12 : hh;
  const m = mm.toString().padStart(2, "0");
  return `${h}:${m} ${period}`;
}

function nextOccurrence(
  schedule: MbSchedule,
  now: Date = new Date(),
): NextOccurrence | null {
  if (!schedule.is_enabled) return null;
  if (!schedule.days_of_week || schedule.days_of_week.length === 0) return null;

  const [hhStr, mmStr] = (schedule.time ?? "").split(":");
  const hh = Number(hhStr);
  const mm = Number(mmStr);
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) return null;

  const tz = schedule.timezone || "UTC";
  const days = new Set(schedule.days_of_week.map((d) => d.toLowerCase()));

  let tzName: string;
  try {
    tzName = partsInTz(now, tz).tzName;
  } catch {
    return null;
  }

  for (let offset = 0; offset < 14; offset++) {
    const candidate = new Date(now.getTime() + offset * 24 * 3600 * 1000);
    let weekday: string;
    let curHour = 0;
    let curMin = 0;
    try {
      const p = partsInTz(candidate, tz);
      weekday = p.weekday;
      if (offset === 0) {
        curHour = p.hour;
        curMin = p.minute;
      }
    } catch {
      return null;
    }
    if (!days.has(weekday)) continue;
    if (offset === 0 && (curHour > hh || (curHour === hh && curMin >= mm))) {
      continue;
    }

    // Build the absolute Date for sort comparisons. The candidate already
    // sits on the right calendar day for `tz`; replace its time-of-day in
    // that timezone with hh:mm.
    const at = new Date(candidate);
    const offsetMinutes = (curHour - hh) * 60 + (curMin - mm); // current vs target
    if (offset === 0) {
      // Same day: shift by the diff so the result lands on hh:mm in `tz`.
      at.setTime(candidate.getTime() - offsetMinutes * 60 * 1000);
    } else {
      // Future day: anchor noon in `tz` then shift to hh:mm.
      const noon = partsInTz(candidate, tz);
      const minsFromNoon = (hh - noon.hour) * 60 + (mm - noon.minute);
      at.setTime(candidate.getTime() + minsFromNoon * 60 * 1000);
    }

    const dayLabel =
      offset === 0
        ? "Today"
        : offset === 1
          ? "Tomorrow"
          : DAY_KEYS.indexOf(weekday as (typeof DAY_KEYS)[number]) >= 0
            ? weekday.charAt(0).toUpperCase() + weekday.slice(1)
            : weekday;
    const display = `${dayLabel} · ${formatTime12(hh, mm)} ${tzName}`;
    return { schedule, at, display };
  }
  return null;
}

export function formatNextBriefing(
  schedule: MbSchedule | null | undefined,
  now: Date = new Date(),
): string {
  if (!schedule) return "—";
  const next = nextOccurrence(schedule, now);
  return next?.display ?? "—";
}

export function pickEarliestNextBriefing(
  schedules: MbSchedule[] | null | undefined,
  now: Date = new Date(),
): NextOccurrence | null {
  if (!schedules || schedules.length === 0) return null;
  let best: NextOccurrence | null = null;
  for (const s of schedules) {
    const n = nextOccurrence(s, now);
    if (!n) continue;
    if (best === null || n.at.getTime() < best.at.getTime()) {
      best = n;
    }
  }
  return best;
}
