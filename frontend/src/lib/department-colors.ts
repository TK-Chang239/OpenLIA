/**
 * Department badge tint classes. Spec §Report Entry Row → Department badge.
 * Each department slug maps to a distinct muted Tailwind class string.
 */
export type DepartmentSlug =
  | "equity_research"
  | "earnings_update"
  | "morning_briefing"
  | "retail_sentiment"
  | "secretary"
  | "macro_research"
  | "panic_thermometer";

const BADGE_CLASS: Record<string, string> = {
  equity_research: "bg-[--color-info]/10 text-[--color-info]",
  earnings_update: "bg-[--color-success]/10 text-[--color-success]",
  macro_research: "bg-[--color-warning]/10 text-[--color-warning]",
  morning_briefing: "bg-[--color-accent-subtle] text-[--color-accent-primary]",
  retail_sentiment: "bg-[--color-info]/10 text-[--color-info]",
  secretary: "bg-[--color-surface-hover] text-[--color-text-secondary]",
  panic_thermometer: "bg-[--color-feedback-error]/10 text-[--color-feedback-error]",
};

const FALLBACK = "bg-[--color-surface-hover] text-[--color-text-secondary]";

export function departmentBadgeClass(slug: string): string {
  return BADGE_CLASS[slug] ?? FALLBACK;
}

const LABELS: Record<string, string> = {
  equity_research: "Equity Research",
  earnings_update: "Earnings Update",
  morning_briefing: "Morning Briefing",
  retail_sentiment: "Retail Sentiment",
  secretary: "Secretary",
  macro_research: "Macro Research",
  panic_thermometer: "Panic Thermometer",
};

export function departmentLabel(slug: string): string {
  return LABELS[slug] ?? slug;
}
