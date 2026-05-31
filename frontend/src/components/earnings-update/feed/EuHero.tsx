import { useTranslation } from "react-i18next";

interface Props {
  reportsThisWeek: number | null;
  trackedTickers: number | null;
  upcomingThisWeek: number | null;
  watchlistEmpty: boolean;
}

const DASH = "—";

export function EuHero({
  reportsThisWeek,
  trackedTickers,
  upcomingThisWeek,
  watchlistEmpty,
}: Props) {
  const { t } = useTranslation();
  const lede = watchlistEmpty
    ? t("earnings.feed.hero_lede_empty")
    : t("earnings.feed.hero_lede");

  return (
    <section className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-end pb-[22px] border-b border-[--color-border-subtle] mb-6">
      <div>
        <span
          className="inline-flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-feedback-success] mb-2.5"
          data-testid="eu-hero-eyebrow"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_0_4px_rgba(var(--color-accent-primary-rgb),0.18)]" />
          {t("earnings.feed.hero_eyebrow")} {String.fromCharCode(0xb7)}{" "}
          {t("earnings.feed.hero_dept")}
        </span>
        <h1 className="text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] m-0 mb-2 text-[--color-text-primary]">
          {t("earnings.feed.hero_headline")}
        </h1>
        <p className="text-base text-[--color-text-secondary] m-0 max-w-[620px] leading-[1.55]">
          {lede}
        </p>
      </div>
      <div className="flex gap-7">
        <Stat label={t("earnings.feed.stat_reports_wk")} value={reportsThisWeek ?? DASH} />
        <Stat label={t("earnings.feed.stat_tracked")} value={trackedTickers ?? DASH} />
        <Stat label={t("earnings.feed.stat_upcoming")} value={upcomingThisWeek ?? DASH} />
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
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
