// The demo "now" is the real current instant, so relative-time labels and the
// app's date-based grouping (e.g. Earnings Update "Today" / upcoming calendar)
// stay correct and the demo always feels current. All fake timestamps derive
// from this via the helpers below.

export const DEMO_NOW = new Date();
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

/** Local "YYYY-MM-DD" for `days` from now (negative = past). Matches the
 *  calendar's local date keys, e.g. for Earnings Update upcoming events. */
export function dateKeyAhead(days: number): string {
  const d = new Date(DEMO_NOW_MS + days * 86_400_000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Small promise sleep used by the streaming shims to pace replays. */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
