import { deleteSchedule, putSchedule } from "../../../api/macro_research";

// Refresh cadence drives the per-user assessment schedule (a singleton cron
// shared across every dashboard template). "weekly"/"monthly" persist a cron
// via the schedule API so the engine regenerates on that calendar; "auto"
// clears the cron and falls back to live in-session polling.
//
// Drives the page-header refresh-cadence dropdown (MacroResearch). The schedule
// has a single home in the header; settings no longer carries a duplicate.
export type CadenceMode = "weekly" | "monthly" | "auto";

export const WEEKLY_CRON = "0 0 * * 0"; // Sunday 00:00
export const MONTHLY_CRON = "0 0 1 * *"; // 1st of month 00:00

// Display order for both the dropdown and the radio selector.
export const CADENCE_ORDER: CadenceMode[] = ["weekly", "monthly", "auto"];

export const CADENCE_LABEL_KEY: Record<CadenceMode, string> = {
  weekly: "macro.refresh_weekly",
  monthly: "macro.refresh_monthly",
  auto: "macro.refresh_auto",
};

export function cronToMode(cron: string | null | undefined): CadenceMode {
  if (cron === WEEKLY_CRON) return "weekly";
  if (cron === MONTHLY_CRON) return "monthly";
  // null (no schedule) and any unrecognized cron both present as auto; an
  // unrecognized cron is left untouched until the user explicitly changes it.
  return "auto";
}

export async function applyCadence(mode: CadenceMode): Promise<void> {
  if (mode === "weekly") await putSchedule(WEEKLY_CRON);
  else if (mode === "monthly") await putSchedule(MONTHLY_CRON);
  else await deleteSchedule();
}
