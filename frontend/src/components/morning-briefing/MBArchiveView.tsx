import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbSchedule, RecentReport } from "../../api/morning-briefing";
import { DEMO_BRIEFING_META } from "../../lib/morning-briefing/demo-data";
import { pickEarliestNextBriefing } from "../../lib/morning-briefing/next-briefing";
import { MBHeroCard } from "./MBHeroCard";
import { MBReportCard } from "./MBReportCard";

interface MBArchiveViewProps {
  reports: RecentReport[];
  loading: boolean;
  schedules?: MbSchedule[];
  onOpen: (report: RecentReport) => void;
  onGoToSettings?: () => void;
}

interface DayGroup {
  key: string;
  heading: string;
  reports: RecentReport[];
}

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function dayHeading(
  date: Date,
  today: Date,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  const tStart = startOfDay(today);
  const dStart = startOfDay(date);
  const diffDays = Math.round(
    (tStart.getTime() - dStart.getTime()) / (24 * 3600 * 1000),
  );
  const weekday = date.toLocaleDateString(undefined, { weekday: "long" });
  const monthDayYear = date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  if (diffDays === 0)
    return t("morning_briefing.archive.today_prefix", {
      date: `${weekday}, ${monthDayYear}`,
    });
  if (diffDays === 1)
    return t("morning_briefing.archive.yesterday_prefix", {
      date: `${weekday}, ${monthDayYear}`,
    });
  return date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
  });
}

function groupReports(
  reports: RecentReport[],
  today: Date,
  t: (key: string, opts?: Record<string, unknown>) => string,
): DayGroup[] {
  const map = new Map<string, RecentReport[]>();
  for (const r of reports) {
    const date = new Date(r.created_at);
    const key = startOfDay(date).toISOString();
    const list = map.get(key) ?? [];
    list.push(r);
    map.set(key, list);
  }
  const out: DayGroup[] = [];
  for (const [key, list] of map) {
    const date = new Date(key);
    list.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    out.push({ key, heading: dayHeading(date, today, t), reports: list });
  }
  out.sort((a, b) => (a.key < b.key ? 1 : -1));
  return out;
}

function SunIcon({ size = 40 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      data-testid="mb-empty-sun"
      style={{ color: "var(--color-text-tertiary)" }}
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function searchMatches(report: RecentReport, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (report.title.toLowerCase().includes(q)) return true;
  const summary = DEMO_BRIEFING_META[report.id]?.summary?.toLowerCase() ?? "";
  if (summary.includes(q)) return true;
  return false;
}

export function MBArchiveView({
  reports,
  loading,
  schedules,
  onOpen,
  onGoToSettings,
}: MBArchiveViewProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");

  const filtered = useMemo(
    () => reports.filter((r) => searchMatches(r, search)),
    [reports, search],
  );

  const today = useMemo(() => new Date(), []);
  const groups = useMemo(
    () => groupReports(filtered, today, t),
    [filtered, today, t],
  );

  if (loading) {
    return (
      <div
        className="text-sm"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        {t("morning_briefing.archive.loading")}
      </div>
    );
  }
  if (reports.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center text-center py-20 gap-3.5"
        data-testid="mb-archive-empty"
      >
        <div
          className="w-14 h-14 rounded-[14px] border bg-[--color-bg-elevated] flex items-center justify-center"
          style={{ borderColor: "var(--color-border-subtle)" }}
        >
          <SunIcon size={24} />
        </div>
        <h3 className="text-[17px] font-medium m-0 text-[--color-text-primary]">
          {t("morning_briefing.archive.empty_title")}
        </h3>
        <p
          className="text-[14px] m-0 max-w-[460px] leading-[1.55]"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {t("morning_briefing.archive.empty_sub")}
        </p>
        {onGoToSettings && (
          <button
            type="button"
            onClick={onGoToSettings}
            className="text-sm underline mt-1"
            data-testid="mb-empty-go-to-settings"
          >
            {t("morning_briefing.archive.go_to_settings")}
          </button>
        )}
      </div>
    );
  }

  const todayLabel = today.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const nextOccurrence = pickEarliestNextBriefing(schedules ?? [], today);
  const nextBriefing = nextOccurrence?.display ?? "—";
  const activeSchedules = (schedules ?? []).filter((s) => s.is_enabled).length;

  const heroReport = !search.trim() && groups.length > 0 ? groups[0].reports[0] : null;
  const restGroups = heroReport
    ? groups.map((g, i) =>
        i === 0
          ? { ...g, reports: g.reports.slice(1) }
          : g,
      )
    : groups;

  return (
    <div className="max-w-[1200px] mx-auto px-8 pt-6 pb-12">
      <div
        className="flex items-center gap-[18px] flex-wrap pb-[18px] mb-[22px] border-b animate-feed-fade-up"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <Stat label={t("morning_briefing.archive.today_label")} value={todayLabel} />
        <Divider />
        <Stat
          label={t("morning_briefing.archive.next_briefing_label")}
          value={nextBriefing}
          mono
        />
        <Divider />
        <Stat
          label={t("morning_briefing.archive.active_schedules_label")}
          value={String(activeSchedules)}
          mono
        />
        <label
          className="ml-auto inline-flex items-center gap-2 h-8 px-3 rounded-md border bg-[--color-bg-input] text-[13px] min-w-[240px]"
          style={{ borderColor: "var(--color-border-secondary)" }}
        >
          <Search size={14} className="text-[--color-text-tertiary]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("morning_briefing.archive.search_placeholder")}
            className="flex-1 bg-transparent border-0 outline-0 text-[13px] text-[--color-text-primary] placeholder:text-[--color-text-tertiary] min-w-0"
            data-testid="mb-archive-search"
          />
        </label>
      </div>

      {heroReport ? (
        <div
          className="mb-[22px] animate-feed-fade-up"
          style={{ animationDelay: "80ms" }}
        >
          <MBHeroCard report={heroReport} onOpen={onOpen} />
        </div>
      ) : null}

      <div className="space-y-[22px]">
        {restGroups.map((g, gi) => {
          if (g.reports.length === 0) return null;
          const delay = 160 + gi * 80;
          return (
            <section
              key={g.key}
              className="animate-feed-fade-up"
              style={{ animationDelay: `${delay}ms` }}
            >
              <h3
                className="m-0 mb-3 text-[13px] font-medium flex items-baseline gap-2"
                style={{ color: "var(--color-text-secondary)" }}
                data-testid={`mb-archive-group-${g.key}`}
              >
                <span className="text-[--color-text-primary] font-medium">
                  {g.heading}
                </span>
                <span
                  className="font-mono text-[10px] tracking-[0.08em]"
                  style={{ color: "var(--color-text-tertiary)" }}
                >
                  ·{" "}
                  {t("morning_briefing.archive.reports_count", {
                    count: g.reports.length,
                  })}
                </span>
              </h3>
              <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
                {g.reports.map((r) => (
                  <MBReportCard key={r.id} report={r} onOpen={onOpen} />
                ))}
              </div>
            </section>
          );
        })}
        {groups.length === 0 ? (
          <p
            className="text-sm py-8 text-center"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            {t("morning_briefing.archive.no_match")}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className="font-mono text-[9.5px] tracking-[0.12em] uppercase"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        {label}
      </span>
      <span
        className={`text-[15px] font-medium text-[--color-text-primary] ${mono ? "font-mono tabular-nums" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

function Divider() {
  return (
    <span
      className="w-px h-7"
      style={{ background: "var(--color-border-subtle)" }}
    />
  );
}
