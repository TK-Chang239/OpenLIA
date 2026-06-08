/**
 * Allowed department slugs across the OpenLIA backend.
 *
 * Single source of truth for the seven departments the server's chat router
 * accepts. Both the static union and the runtime tuple are exported so call
 * sites can use whichever they need (TypeScript narrowing vs. validation).
 */

export const DEPARTMENT_SLUGS = [
  "secretary",
  "equity_research",
  "earnings_update",
  "morning_briefing",
  "retail_sentiment",
  "macro_research",
  "panic_thermometer",
] as const;

export type DepartmentSlug = (typeof DEPARTMENT_SLUGS)[number];

export const isDepartmentSlug = (value: string): value is DepartmentSlug =>
  (DEPARTMENT_SLUGS as readonly string[]).includes(value);

