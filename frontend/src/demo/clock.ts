// A fixed "as of" instant so the demo never looks stale. All fake timestamps
// are derived from this so lists, charts, and relative-time labels stay
// internally consistent no matter when the demo is opened.

export const DEMO_NOW = new Date("2026-08-07T15:45:00-04:00");
export const DEMO_NOW_ISO = DEMO_NOW.toISOString();
export const DEMO_NOW_MS = DEMO_NOW.getTime();

/** ISO string for a moment `mins` minutes before the frozen now. */
export function minsAgo(mins: number): string {
  return new Date(DEMO_NOW_MS - mins * 60_000).toISOString();
}

/** ISO string for a moment `hours` hours before the frozen now. */
export function hoursAgo(hours: number): string {
  return minsAgo(hours * 60);
}

/** ISO string for a moment `days` days before the frozen now. */
export function daysAgo(days: number): string {
  return minsAgo(days * 60 * 24);
}

/** Small promise sleep used by the streaming shims to pace replays. */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
