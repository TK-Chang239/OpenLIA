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

/** Department badge tint classes. Per Repository design palette: each dept
 *  gets a tinted bg + matching text + subtle border in the same hue family.
 *  All three properties read from per-dept tokens so the recipe flips per
 *  theme — see tokens.css [data-theme="dark"] block. */
const BLUE = "bg-[--color-dept-blue-bg] text-[--color-dept-blue-text] border border-[--color-dept-blue-border]";
const ORANGE = "bg-[--color-dept-orange-bg] text-[--color-dept-orange-text] border border-[--color-dept-orange-border]";
const PURPLE = "bg-[--color-dept-purple-bg] text-[--color-dept-purple-text] border border-[--color-dept-purple-border]";
const ACCENT_OLIVE = "bg-[--color-dept-accent-bg-soft] text-[--color-accent-on-tint] border border-[--color-dept-accent-border-soft]";
const ACCENT_BRIGHT = "bg-[--color-dept-accent-bg-strong] text-[--color-accent-on-tint] border border-[--color-dept-accent-border-strong]";
const ERROR = "bg-[--color-dept-error-bg] text-[--color-dept-error-text] border border-[--color-dept-error-border]";

const BADGE_CLASS: Record<string, string> = {
  equity_research: BLUE,
  retail_sentiment: BLUE,
  earnings_update: ACCENT_OLIVE,
  morning_briefing: ACCENT_BRIGHT,
  macro_research: ORANGE,
  secretary: PURPLE,
  panic_thermometer: ERROR,
};

const FALLBACK = "bg-[--color-surface-hover] text-[--color-text-secondary] border border-[--color-border-subtle]";

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
