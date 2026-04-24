import type { DashboardResult } from "../../../../api/macro_research";

export function makeResult(
  overrides: Partial<DashboardResult> & Pick<DashboardResult, "slug">,
): DashboardResult {
  return {
    display_name: overrides.slug,
    severity: "green",
    tiers: [],
    headline: null,
    generated_at: "2026-04-24T00:00:00+00:00",
    smart_mode_active: false,
    ...overrides,
  };
}
