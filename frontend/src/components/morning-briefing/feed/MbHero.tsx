import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  briefingsThisWeek: number;
  activeSchedules: number;
  /** Pre-formatted "soonest enabled run" display string, or null when none. */
  nextRun: string | null;
}

const DASH = "—";

export function MbHero({ briefingsThisWeek, activeSchedules, nextRun }: Props) {
  const { t } = useTranslation();
  return (
    <section
      data-testid="mb-hero"
      className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-end pb-[22px] border-b border-[--color-border-subtle] mb-6"
    >
      <div>
        <span className="inline-flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-feedback-success] mb-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_0_4px_rgba(var(--color-accent-primary-rgb),0.18)]" />
          {t("morning_briefing.hero.eyebrow")} {String.fromCharCode(0xb7)}{" "}
          {t("morning_briefing.hero.dept")}
        </span>
        <h1 className="text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] m-0 mb-2 text-[--color-text-primary]">
          {t("morning_briefing.hero.headline")}
        </h1>
        <p className="text-base text-[--color-text-secondary] m-0 max-w-[620px] leading-[1.55]">
          {t("morning_briefing.hero.lede")}
        </p>
      </div>
      <div className="flex gap-7">
        <Stat
          label={t("morning_briefing.hero.stat_briefings_wk")}
          value={briefingsThisWeek}
        />
        <Stat
          label={t("morning_briefing.hero.stat_active_schedules")}
          value={activeSchedules}
        />
        {/* Next run is a phrase, not a metric — render it smaller so a long
            "Tomorrow · 7:00 AM EST" string never blows out the stat row. */}
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-[9.5px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
            {t("morning_briefing.hero.stat_next_run")}
          </span>
          <span className="font-mono text-[13px] leading-[1.3] text-[--color-text-primary] max-w-[180px]">
            {nextRun ?? DASH}
          </span>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9.5px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
        {label}
      </span>
      <span className="font-mono text-[22px] tabular-nums leading-none text-[--color-text-primary]">
        {value}
      </span>
    </div>
  );
}
