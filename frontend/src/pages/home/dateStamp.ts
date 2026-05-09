/** Format a Date as the design's mono date stamp:
 *  `TUE · 06 MAY 2026`  (uppercase, en-US weekday/month abbreviations). */
const WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const MONTHS = [
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

export function formatDateStamp(d: Date = new Date()): string {
  const wd = WEEKDAYS[d.getDay()];
  const dd = String(d.getDate()).padStart(2, "0");
  const mo = MONTHS[d.getMonth()];
  const yy = d.getFullYear();
  return `${wd} · ${dd} ${mo} ${yy}`;
}
