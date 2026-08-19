import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Briefcase,
  FileBarChart,
  Search,
  Settings as SettingsIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  deleteRun,
  type RunSummary,
  syncWatchlist,
} from "../../api/earnings-update";
import { ConfirmDialog } from "../../components/primitives/ConfirmDialog";
import { CoverageDrawer } from "../../components/earnings-update/CoverageDrawer";
import { EUCabinetView } from "../../components/earnings-update/EUCabinetView";
import { EuRefreshButton } from "../../components/earnings-update/EuRefreshButton";
import { OnDemandReportModal } from "../../components/earnings-update/OnDemandReportModal";
import { ReportSettingsModal } from "../../components/earnings-update/ReportSettingsModal";
import { EuCalendar } from "../../components/earnings-update/calendar/EuCalendar";
import { EuBigCard } from "../../components/earnings-update/feed/EuBigCard";
import { EuGeneratingCard } from "../../components/earnings-update/feed/EuGeneratingCard";
import { EuEmptyPage } from "../../components/earnings-update/feed/EuEmptyPage";
import {
  EuFeedSection,
  EuSectionEmpty,
} from "../../components/earnings-update/feed/EuFeedSection";
import { EuHero } from "../../components/earnings-update/feed/EuHero";
import { EuReportRow } from "../../components/earnings-update/feed/EuReportRow";
import { EuUpNextCard } from "../../components/earnings-update/feed/EuUpNextCard";
import { EuViewToggle, type EuView } from "../../components/earnings-update/feed/EuViewToggle";
import {
  groupReports,
  searchReports,
} from "../../components/earnings-update/feed/feedHelpers";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useEuRuns } from "../../hooks/useEuRuns";
import { useEuRunStream } from "../../hooks/useEuRunStream";
import { useEuSchedule } from "../../hooks/useEuSchedule";
import { useEuSettings } from "../../hooks/useEuSettings";
import { useEuWatchlist } from "../../hooks/useEuWatchlist";

interface LiveCard {
  ticker: string;
  reportId: string;
}

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function findRun(runs: RunSummary[], reportId: string): RunSummary | undefined {
  return runs.find((r) => r.report_id === reportId);
}

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      data-testid="eu-skeleton"
      className={`ol-skeleton ${className}`}
    />
  );
}

export default function EarningsUpdate() {
  const { t } = useTranslation();
  const {
    entries,
    add,
    remove,
    loading: watchlistLoading,
    error: watchlistError,
    refresh: refreshWatchlist,
  } = useEuWatchlist();
  const {
    runs,
    refresh: refreshRuns,
    loading: runsLoading,
    error: runsError,
    disabled: runsDisabled,
  } = useEuRuns();
  const { settings, save: saveSettings, disabled: settingsDisabled } =
    useEuSettings();
  const { schedule, byTicker, refresh: refreshSchedule } = useEuSchedule();

  const [coverageOpen, setCoverageOpen] = useState(false);
  const [cabinetOpen, setCabinetOpen] = useState(false);
  const [onDemandOpen, setOnDemandOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [live, setLive] = useState<LiveCard | null>(null);
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);
  const [view, setView] = useState<EuView>("stream");
  const [search, setSearch] = useState("");

  const fv = useFileViewer();
  const stream = useEuRunStream(live?.reportId ?? null);

  const removeReport = useCallback(
    async (reportId: string) => {
      await deleteRun(reportId);
      await refreshRuns();
    },
    [refreshRuns],
  );

  const openReport = useCallback(
    (reportId: string) => {
      const match = findRun(runs, reportId);
      fv.open({
        filename: match?.subject ?? "Earnings Update",
        kind: "report",
        metadata: match ? `EU v2 · ${match.ticker}` : "Earnings Update",
        source: { kind: "eu_v2_report", reportId },
        onDelete: () => removeReport(reportId),
      });
    },
    [fv, runs, removeReport],
  );

  const retryFetch = useCallback(() => {
    void refreshWatchlist();
    void refreshRuns();
  }, [refreshWatchlist, refreshRuns]);

  const handleRefreshDates = useCallback(async () => {
    const { synced } = await syncWatchlist();
    await Promise.all([refreshWatchlist(), refreshSchedule()]);
    return synced;
  }, [refreshWatchlist, refreshSchedule]);

  useEffect(() => {
    if (stream.status === "completed") {
      void refreshRuns();
    } else if (stream.status === "cancelled" || stream.status === "failed") {
      // Cancelled/failed runs have no completed card to show — dismiss the
      // live card so it doesn't linger as a frozen generating card, and
      // refresh so any partial report surfaces in the feed.
      setLive(null);
      void refreshRuns();
    }
  }, [stream.status, refreshRuns]);

  const filtered = useMemo(() => searchReports(runs, search), [runs, search]);
  const groups = useMemo(() => groupReports(filtered), [filtered]);
  const searching = search.trim().length > 0;

  const todayReports = useMemo(
    () =>
      live ? groups.today.filter((r) => r.report_id !== live.reportId) : groups.today,
    [groups.today, live],
  );

  const heroToday = !live && todayReports.length > 0 ? todayReports[0] : null;
  const restToday = heroToday ? todayReports.slice(1) : todayReports;

  const upNext = useMemo(() => {
    // Guard against stale rows the server may still return: "up next"
    // means pending AND actually in the future.
    const now = Date.now();
    return schedule.filter((s) => {
      if (s.status !== "pending") return false;
      const ts = new Date(s.scheduled_run_at).getTime();
      return !Number.isNaN(ts) && ts >= now;
    });
  }, [schedule]);

  const reportsThisWeek = useMemo(() => {
    const now = Date.now();
    return runs.filter((r) => {
      const ts = new Date(r.created_at).getTime();
      return !Number.isNaN(ts) && now - ts < WEEK_MS;
    }).length;
  }, [runs]);

  const upcomingThisWeek = useMemo(() => {
    const now = Date.now();
    return schedule.filter((s) => {
      if (s.status !== "pending") return false;
      const ts = new Date(s.scheduled_run_at).getTime();
      return !Number.isNaN(ts) && ts - now < WEEK_MS && ts >= now;
    }).length;
  }, [schedule]);

  const liveCount = useMemo(() => {
    // Exclude the active live card's run so it isn't counted twice once it
    // shows up in the runs list as "running".
    const running = runs.filter(
      (r) => r.status === "running" && r.report_id !== live?.reportId,
    ).length;
    return running + (live ? 1 : 0);
  }, [runs, live]);

  const disabled = runsDisabled || settingsDisabled;
  const hasError = Boolean(watchlistError || runsError);
  const initialLoading = watchlistLoading || runsLoading;
  const allEmpty =
    !initialLoading &&
    !hasError &&
    !disabled &&
    entries.length === 0 &&
    runs.length === 0 &&
    !live;

  function formatHeroStamp(iso: string): string {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const date = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    const time = d
      .toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
      .replace(/^0/, "");
    return `${date} · ${time} ET`;
  }

  const liveTitle =
    stream.status === "completed"
      ? t("earnings.report_ready")
      : t("earnings.generating_report", { ticker: live?.ticker ?? "" });

  return (
    <div className="flex flex-col h-full">
      <header className="h-[52px] flex items-center gap-3 px-6 flex-shrink-0 border-b border-[--color-border-subtle]">
        <h1 className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
          {t("earnings.title")}
        </h1>
        <div className="flex-1" />
        {liveCount > 0 ? (
          <span
            data-testid="eu-live-pill"
            className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.08em] uppercase text-[--color-feedback-success]"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
            {t("earnings.live_pill", { count: liveCount })}
          </span>
        ) : null}
        <EuRefreshButton
          onRefresh={handleRefreshDates}
          disabled={entries.length === 0}
        />
        <button
          type="button"
          onClick={() => setCoverageOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <Briefcase size={13} /> {t("earnings.watchlist")}
          <span className="font-mono text-[10px] text-[--color-text-tertiary]">
            {entries.length}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setOnDemandOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal] text-[12.5px] font-medium"
        >
          <FileBarChart size={13} /> {t("earnings.generate_report")}
        </button>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          aria-label={t("earnings.report_settings_aria")}
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <SettingsIcon size={13} /> {t("earnings.settings")}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-8 pt-7 pb-16">
          {disabled ? (
            <div
              data-testid="eu-v2-disabled-banner"
              className="mb-4 flex items-center gap-3 border border-[--color-border-subtle] rounded-[--radius-md] px-4 py-2.5 text-sm text-[--color-text-secondary] bg-[--color-surface-hover]"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[--color-feedback-warning] flex-shrink-0" />
              {t("earnings.disabled_banner")}
            </div>
          ) : null}

          {hasError ? (
            <div
              role="alert"
              className="mb-4 flex items-center justify-between gap-4 border border-[--color-feedback-error] rounded-[--radius-md] px-4 py-2 text-sm text-[--color-feedback-error]"
            >
              <span>{t("earnings.load_failed")}</span>
              <button
                type="button"
                onClick={retryFetch}
                className="text-sm font-medium underline"
              >
                {t("earnings.retry")}
              </button>
            </div>
          ) : null}

          {initialLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-[140px]" />
              <Skeleton className="h-12" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          ) : allEmpty ? (
            <>
              <div className="animate-feed-fade-up">
                <EuHero
                  reportsThisWeek={null}
                  trackedTickers={null}
                  upcomingThisWeek={null}
                  watchlistEmpty
                />
              </div>
              <div className="animate-feed-fade-up" style={{ animationDelay: "120ms" }}>
                <EuEmptyPage onOpenWatchlist={() => setCoverageOpen(true)} />
              </div>
            </>
          ) : (
            <>
              <div className="animate-feed-fade-up">
                <EuHero
                  reportsThisWeek={runs.length === 0 ? null : reportsThisWeek}
                  trackedTickers={entries.length}
                  upcomingThisWeek={upcomingThisWeek}
                  watchlistEmpty={entries.length === 0}
                />
              </div>

              <div
                className="animate-feed-fade-up flex items-center gap-2 flex-wrap mb-[22px]"
                style={{ animationDelay: "80ms" }}
              >
                <EuViewToggle view={view} onChange={setView} />
                <div className="flex-1" />
                {view === "stream" ? (
                  <div className="inline-flex items-center gap-2 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-[--color-bg-elevated] min-w-[220px]">
                    <Search size={13} className="text-[--color-text-tertiary]" />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder={t("earnings.feed.search_placeholder")}
                      aria-label={t("earnings.feed.search_aria")}
                      className="border-0 bg-transparent outline-none text-[13px] text-[--color-text-primary] w-full placeholder:text-[--color-text-tertiary]"
                    />
                  </div>
                ) : null}
              </div>

              {view === "calendar" ? (
                <div className="animate-feed-fade-up" style={{ animationDelay: "120ms" }}>
                  <EuCalendar
                    schedule={schedule}
                    runs={runs}
                    onOpenReport={openReport}
                  />
                </div>
              ) : (
                <>
                  <div
                    className="animate-feed-fade-up"
                    style={{ animationDelay: "160ms" }}
                  >
                    <EuFeedSection
                      label={t("earnings.today")}
                      count={todayReports.length + (live ? 1 : 0)}
                    >
                      {live ? (
                        <div className="mb-2">
                          {stream.status === "completed" ? (
                            <EuBigCard
                              ticker={live.ticker}
                              title={liveTitle}
                              status="complete"
                              reportId={live.reportId}
                              highlights={findRun(runs, live.reportId)?.highlights ?? null}
                              onOpen={openReport}
                              onRemove={(id) => setPendingRemoval(id)}
                            />
                          ) : (
                            <EuGeneratingCard ticker={live.ticker} stream={stream} />
                          )}
                        </div>
                      ) : null}
                      {heroToday ? (
                        <div className="mb-2">
                          <EuBigCard
                            ticker={heroToday.ticker}
                            title={heroToday.subject}
                            stamp={formatHeroStamp(heroToday.created_at)}
                            status="complete"
                            reportId={heroToday.report_id}
                            highlights={heroToday.highlights ?? null}
                            onOpen={openReport}
                            onRemove={(id) => setPendingRemoval(id)}
                          />
                        </div>
                      ) : null}
                      {todayReports.length === 0 && !live ? (
                        <EuSectionEmpty
                          message={
                            searching
                              ? t("earnings.no_matching_prints_today")
                              : t("earnings.no_prints_today")
                          }
                        />
                      ) : null}
                      {restToday.length > 0 ? (
                        <div className="flex flex-col gap-2">
                          {restToday.map((r) => (
                            <EuReportRow
                              key={r.report_id}
                              report={r}
                              onOpen={openReport}
                              onRemove={(id) => setPendingRemoval(id)}
                            />
                          ))}
                        </div>
                      ) : null}
                    </EuFeedSection>
                  </div>

                  <div
                    className="animate-feed-fade-up"
                    style={{ animationDelay: "240ms" }}
                  >
                    <EuFeedSection
                      label={t("earnings.up_next_24h")}
                      count={upNext.length}
                    >
                      {upNext.length === 0 ? (
                        <EuSectionEmpty message={t("earnings.no_upcoming_earnings")} />
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          {upNext.map((u) => (
                            <EuUpNextCard key={u.id} entry={u} />
                          ))}
                        </div>
                      )}
                    </EuFeedSection>
                  </div>

                  <div
                    className="animate-feed-fade-up"
                    style={{ animationDelay: "320ms" }}
                  >
                    <EuFeedSection
                      label={t("earnings.earlier_this_week")}
                      count={groups.earlierThisWeek.length}
                    >
                      {groups.earlierThisWeek.length === 0 ? (
                        <EuSectionEmpty
                          message={
                            searching
                              ? t("earnings.no_matching_prints")
                              : t("earnings.no_prints_this_week")
                          }
                        />
                      ) : (
                        <div className="flex flex-col gap-2">
                          {groups.earlierThisWeek.map((r) => (
                            <EuReportRow
                              key={r.report_id}
                              report={r}
                              onOpen={openReport}
                              onRemove={(id) => setPendingRemoval(id)}
                            />
                          ))}
                        </div>
                      )}
                    </EuFeedSection>
                  </div>

                  {runs.length > 0 ? (
                    <div className="mt-7 flex justify-center">
                      <button
                        type="button"
                        onClick={() => setCabinetOpen(true)}
                        className="font-mono text-[11px] tracking-[0.12em] uppercase text-[--color-text-secondary] hover:text-[--color-text-primary]"
                      >
                        {t("earnings.view_all_reports")}
                      </button>
                    </div>
                  ) : null}
                </>
              )}
            </>
          )}
        </div>
      </div>

      <CoverageDrawer
        open={coverageOpen}
        entries={entries}
        byTicker={byTicker}
        runs={runs}
        onClose={() => setCoverageOpen(false)}
        onAdd={async (ticker) => {
          await add(ticker);
        }}
        onRemove={async (id) => {
          await remove(id);
        }}
        onOpenReport={openReport}
      />

      <OnDemandReportModal
        open={onDemandOpen}
        watchlist={entries}
        onClose={() => setOnDemandOpen(false)}
        onStarted={(reportId, ticker) => {
          setLive({ reportId, ticker });
        }}
      />

      {cabinetOpen ? (
        <EUCabinetView
          reports={runs}
          onBack={() => setCabinetOpen(false)}
          onOpenReport={openReport}
          onRemove={async (id) => {
            await removeReport(id);
          }}
        />
      ) : null}

      {settingsOpen && settings ? (
        <ReportSettingsModal
          settings={settings}
          onClose={() => setSettingsOpen(false)}
          onSave={saveSettings}
        />
      ) : null}

      <ConfirmDialog
        open={pendingRemoval !== null}
        title={t("earnings.cabinet.remove_title")}
        description={t("earnings.cabinet.remove_description")}
        confirmLabel={t("earnings.cabinet.remove_confirm")}
        destructive
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() => {
          const id = pendingRemoval;
          setPendingRemoval(null);
          if (!id) return;
          if (id === live?.reportId) setLive(null);
          void removeReport(id);
        }}
      />
    </div>
  );
}
