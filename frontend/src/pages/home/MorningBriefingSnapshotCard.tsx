import { useEffect, useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  listMbRuns,
  type MbCoverMetric,
  type MbRunSummary,
} from "../../api/morning-briefing";

/** Compact snapshot of the latest Morning Briefing on the Home page.
 *  Backed by the real latest completed run's cover highlights (lede, rating,
 *  key metrics, date). The engine emits prose sections + a cover summary, so
 *  this surfaces the summary and links to the full briefing rather than
 *  fabricating macro/watchlist/calendar columns. */

function metricToneClass(tone: string | null): string {
  const t = (tone ?? "").toLowerCase();
  if (/pos|up|gain|bull|good/.test(t)) return "text-feedback-success";
  if (/neg|down|loss|bear|bad|risk/.test(t)) return "text-feedback-error";
  return "text-text-primary";
}

function editionDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const wd = d.toLocaleDateString(undefined, { weekday: "short" }).toUpperCase();
  const day = String(d.getDate()).padStart(2, "0");
  const mon = d.toLocaleDateString(undefined, { month: "short" }).toUpperCase();
  return `${wd} ${day} ${mon}`;
}

function Shell({
  children,
  ariaLabel,
}: {
  children: React.ReactNode;
  ariaLabel: string;
}): JSX.Element {
  return (
    <article
      aria-label={ariaLabel}
      className="rounded-xl border border-border-subtle bg-bg-elevated overflow-hidden"
    >
      {children}
    </article>
  );
}

export function MorningBriefingSnapshotCard(): JSX.Element {
  const { t } = useTranslation();
  const [run, setRun] = useState<MbRunSummary | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const runs = await listMbRuns("completed");
        if (cancelled) return;
        const latest = [...runs].sort((a, b) =>
          b.created_at.localeCompare(a.created_at),
        )[0];
        setRun(latest ?? null);
      } catch {
        if (!cancelled) setRun(null);
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const ariaLabel = t("home_cards.morning_briefing_aria");

  if (!loaded) {
    return (
      <Shell ariaLabel={ariaLabel}>
        <div className="px-[18px] py-[22px] text-sm text-text-tertiary">
          {t("home_cards.mb_loading")}
        </div>
      </Shell>
    );
  }

  if (!run) {
    return (
      <Shell ariaLabel={ariaLabel}>
        <div className="flex flex-col gap-2 px-[18px] py-[22px]">
          <span className="text-[15px] font-semibold text-text-primary">
            {t("home_cards.mb_empty")}
          </span>
          <span className="text-sm text-text-secondary">
            {t("home_cards.mb_empty_hint")}
          </span>
          <Link
            to="/morning-briefing"
            className="mt-1 inline-flex w-fit items-center gap-[6px] px-[10px] py-1 rounded-md border border-border-subtle text-text-primary no-underline transition-colors duration-normal ease-out hover:border-border-strong hover:bg-surface-hover"
          >
            {t("home_cards.open_briefing")}
            <ArrowRight size={11} strokeWidth={2} />
          </Link>
        </div>
      </Shell>
    );
  }

  const lede = run.highlights?.subtitle || run.subject;
  const rating = run.highlights?.rating;
  const metrics: MbCoverMetric[] = run.highlights?.metrics ?? [];

  return (
    <Shell ariaLabel={ariaLabel}>
      <header className="flex items-center gap-[10px] px-[18px] py-[14px] border-b border-border-subtle">
        <span
          aria-hidden="true"
          className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[5px] bg-accent-primary text-[--color-accent-on] font-mono text-[9px] font-bold shadow-[0_0_8px_rgba(212,255,0,0.35)]"
        >
          LIA
        </span>
        <span className="text-[13.5px] font-semibold text-text-primary tracking-[-0.005em] truncate">
          {run.subject}
        </span>
        <span className="ml-auto flex items-center gap-2 font-mono text-[9.5px] tracking-[0.1em] uppercase text-text-tertiary">
          <span>{editionDate(run.created_at)}</span>
          {rating ? (
            <>
              <span className="w-[3px] h-[3px] rounded-full bg-text-tertiary" />
              <span className="text-feedback-success normal-case tracking-normal">
                {rating}
              </span>
            </>
          ) : null}
        </span>
        <Link
          to="/morning-briefing"
          className="ml-3 inline-flex items-center gap-[6px] px-[10px] py-1 rounded-md border border-border-subtle bg-bg-base font-mono text-[10px] tracking-[0.06em] text-text-primary no-underline transition-colors duration-normal ease-out hover:border-border-strong hover:bg-surface-hover"
        >
          {t("home_cards.open_briefing")}
          <ArrowRight size={11} strokeWidth={2} />
        </Link>
      </header>

      <div className="grid grid-cols-[28px_1fr] gap-3 px-[18px] py-[14px] border-b border-border-subtle">
        <span
          aria-hidden="true"
          className="self-start mt-[2px] inline-flex items-center justify-center w-[22px] h-[22px] rounded-[5px] bg-accent-primary text-[--color-accent-on] font-mono text-[9px] font-bold"
        >
          LIA
        </span>
        <div className="flex flex-col gap-[6px] min-w-0">
          <div className="flex items-center gap-2 font-mono text-[9.5px] tracking-[0.12em] uppercase text-text-tertiary">
            <span>{t("home_cards.todays_read")}</span>
          </div>
          <p className="m-0 text-[16px] leading-[1.4] font-medium text-text-primary tracking-[-0.005em]">
            {lede}
          </p>
        </div>
      </div>

      {metrics.length > 0 ? (
        <div className="flex flex-wrap gap-x-6 gap-y-2 px-[18px] py-[14px]">
          {metrics.slice(0, 4).map((m) => (
            <div key={`${m.label}-${m.value}`} className="flex flex-col gap-[2px]">
              <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-text-tertiary">
                {m.label}
              </span>
              <span className="flex items-baseline gap-2">
                <span className="font-mono text-[15px] font-medium text-text-primary tabular-nums">
                  {m.value}
                </span>
                {m.change ? (
                  <span
                    className={`font-mono text-[10px] tabular-nums ${metricToneClass(m.tone)}`}
                  >
                    {m.change}
                  </span>
                ) : null}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex items-center gap-[14px] px-[18px] py-[10px] border-t border-border-subtle bg-bg-base font-mono text-[10px] tracking-[0.06em] text-text-tertiary uppercase">
        <span>{editionDate(run.created_at)}</span>
        <Link
          to={`/secretary?prompt=${encodeURIComponent("Brief me on today.")}`}
          className="ml-auto inline-flex items-center gap-[6px] px-[10px] py-[3px] rounded-md border border-border-subtle text-text-primary no-underline transition-colors duration-normal ease-out hover:bg-surface-hover hover:border-border-strong"
        >
          {t("home_cards.ask_lia_brief")}
          <MessageSquare size={11} strokeWidth={2} />
        </Link>
      </div>
    </Shell>
  );
}
