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

/**
 * Departments that have a deterministic runner (i.e. a `<dept>.needs.yaml`
 * file resolved by the wizard-time adapter). These are the only departments
 * the Review page renders resolve panels for; chat-driven departments map
 * tools dynamically at runtime via the chat router.
 */
export const RUNNER_BEARING_DEPARTMENTS: readonly DepartmentSlug[] = [
  "retail_sentiment",
] as const;

export const RUNNER_DEPARTMENT_LABELS: Record<DepartmentSlug, string> = {
  secretary: "Secretary",
  equity_research: "Equity Research",
  earnings_update: "Earnings Update",
  morning_briefing: "Morning Briefing",
  retail_sentiment: "Retail Sentiment",
  macro_research: "Macro Research",
  panic_thermometer: "Panic Thermometer",
};
