import { useCallback, useMemo, useState } from "react";
import { Briefcase, Settings as SettingsIcon } from "lucide-react";

import {
  deleteReport,
  startOnDemandReport,
  type RecentReport,
} from "../../api/earnings-update";
import { CoverageModal } from "../../components/earnings-update/CoverageModal";
import { EUCabinetView } from "../../components/earnings-update/EUCabinetView";
import { OnDemandReportModal } from "../../components/earnings-update/OnDemandReportModal";
import { ReportSettingsModal } from "../../components/earnings-update/ReportSettingsModal";
import { EuBigCard } from "../../components/earnings-update/feed/EuBigCard";
import { EuEmptyPage } from "../../components/earnings-update/feed/EuEmptyPage";
import {
  EuFeedSection,
  EuSectionEmpty,
} from "../../components/earnings-update/feed/EuFeedSection";
import { EuFilterStrip } from "../../components/earnings-update/feed/EuFilterStrip";
import { EuHero } from "../../components/earnings-update/feed/EuHero";
import { EuReportRow } from "../../components/earnings-update/feed/EuReportRow";
import { EuUpNextCard } from "../../components/earnings-update/feed/EuUpNextCard";
import {
  applyFilter,
  groupReports,
  type FeedFilter,
} from "../../components/earnings-update/feed/feedHelpers";
import { downloadUrlForReport } from "../../api/files";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useEuConfig } from "../../hooks/useEuConfig";
import { useEuReports } from "../../hooks/useEuReports";
import { useEuWatchlist } from "../../hooks/useEuWatchlist";
import {
  DEMO_REPORT_META,
  getDemoHeroStats,
  getDemoUpNext,
  isDemoMode,
} from "../../lib/earnings-update/demo-data";

interface LiveCard {
  ticker: string;
  status: "streaming" | "complete";
  reportId: string | null;
  title: string;
}

function findReport(
  reports: RecentReport[],
  reportId: string,
): RecentReport | undefined {
  return reports.find((r) => r.id === reportId);
}

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      data-testid="eu-skeleton"
      className={`bg-[--color-surface-hover] rounded-[--radius-md] animate-pulse ${className}`}
    />
  );
}

export default function EarningsUpdate() {
  const {
    entries,
    add,
    remove,
    loading: watchlistLoading,
    error: watchlistError,
    refresh: refreshWatchlist,
  } = useEuWatchlist();
  const {
    reports,
    refresh: refreshReports,
    loading: reportsLoading,
    error: reportsError,
  } = useEuReports(30);
  const { config, save: saveConfig } = useEuConfig();

  const [coverageOpen, setCoverageOpen] = useState(false);
  const [cabinetOpen, setCabinetOpen] = useState(false);
  const [onDemandOpen, setOnDemandOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [liveCard, setLiveCard] = useState<LiveCard | null>(null);
  const [filter, setFilter] = useState<FeedFilter>("all");
  const [search, setSearch] = useState("");

  const fv = useFileViewer();

  const openReport = useCallback(
    (id: string, fallback?: RecentReport) => {
      const match = fallback ?? findReport(reports, id);
      fv.open({
        filename: match?.title ?? "Earnings Update",
        kind: "report",
        metadata: match?.subject ? `EU • ${match.subject}` : "Earnings Update",
        source: { kind: "report", reportId: id },
      });
    },
    [fv, reports],
  );

  const downloadReport = useCallback((id: string) => {
    const a = document.createElement("a");
    a.href = downloadUrlForReport(id);
    a.rel = "noopener";
    a.click();
  }, []);

  const removeReport = useCallback(
    async (id: string) => {
      await deleteReport(id);
      await refreshReports();
    },
    [refreshReports],
  );

  const retryFetch = useCallback(() => {
    void refreshWatchlist();
    void refreshReports();
  }, [refreshWatchlist, refreshReports]);

  const filtered = useMemo(
    () => applyFilter(reports, filter, { watchlist: entries, search }),
    [reports, filter, entries, search],
  );

  const groups = useMemo(() => groupReports(filtered), [filtered]);

  const todayReports = useMemo(
    () =>
      liveCard?.status === "complete" && liveCard.reportId
        ? groups.today.filter((r) => r.id !== liveCard.reportId)
        : groups.today,
    [groups.today, liveCard],
  );

  const demo = isDemoMode();
  const heroToday = !liveCard && todayReports.length > 0 ? todayReports[0] : null;
  const restToday = heroToday ? todayReports.slice(1) : todayReports;
  const heroMeta = heroToday ? DEMO_REPORT_META[heroToday.id] : undefined;
  const upNext = demo ? getDemoUpNext() : [];
  const stats = demo ? getDemoHeroStats() : null;

  const hasError = Boolean(watchlistError || reportsError);
  const initialLoading = watchlistLoading || reportsLoading;
  const allEmpty =
    !initialLoading &&
    !hasError &&
    entries.length === 0 &&
    reports.length === 0 &&
    !liveCard;

  const reportsThisWeek = stats?.reportsThisWeek ?? (reports.length === 0 ? null : reports.length);

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

  return (
    <div className="flex flex-col h-full">
      <header className="h-[52px] flex items-center gap-3.5 px-6 flex-shrink-0 border-b border-[--color-border-subtle]">
        <h1 className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
          Earnings Update
        </h1>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => setCoverageOpen(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <Briefcase size={13} /> Coverage
        </button>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          aria-label="Report settings"
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
        >
          <SettingsIcon size={13} /> Settings
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-8 pt-7 pb-16">
          {hasError ? (
            <div
              role="alert"
              className="mb-4 flex items-center justify-between gap-4 border border-[--color-feedback-error] rounded-[--radius-md] px-4 py-2 text-sm text-[--color-feedback-error]"
            >
              <span>Failed to load earnings data. Try again.</span>
              <button
                type="button"
                onClick={retryFetch}
                className="text-sm font-medium underline"
              >
                Retry
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
                  beats={null}
                  misses={null}
                  avgSurprise={null}
                  avgLatency={null}
                  watchlistEmpty
                />
              </div>
              <div
                className="animate-feed-fade-up"
                style={{ animationDelay: "120ms" }}
              >
                <EuEmptyPage onOpenCoverage={() => setCoverageOpen(true)} />
              </div>
            </>
          ) : (
            <>
              <div className="animate-feed-fade-up">
                <EuHero
                  reportsThisWeek={reportsThisWeek}
                  beats={stats?.beats ?? null}
                  misses={stats?.misses ?? null}
                  avgSurprise={stats?.avgSurprise ?? null}
                  avgLatency={stats?.avgLatency ?? null}
                  watchlistEmpty={entries.length === 0}
                />
              </div>
              <div
                className="animate-feed-fade-up"
                style={{ animationDelay: "80ms" }}
              >
                <EuFilterStrip
                  filter={filter}
                  onFilterChange={setFilter}
                  search={search}
                  onSearchChange={setSearch}
                  onAdHoc={() => setOnDemandOpen(true)}
                />
              </div>

              <div
                className="animate-feed-fade-up"
                style={{ animationDelay: "160ms" }}
              >
              <EuFeedSection
                label="Today's"
                count={todayReports.length + (liveCard ? 1 : 0)}
              >
                {liveCard ? (
                  <div className="mb-2">
                    <EuBigCard
                      ticker={liveCard.ticker}
                      title={liveCard.title}
                      status={liveCard.status}
                      reportId={liveCard.reportId}
                      onOpen={(id) => openReport(id)}
                    />
                  </div>
                ) : null}
                {!liveCard && heroToday ? (
                  <div className="mb-2">
                    <EuBigCard
                      ticker={heroToday.subject ?? ""}
                      title={heroToday.title}
                      subtitle={heroMeta?.summary}
                      stamp={formatHeroStamp(heroToday.created_at)}
                      status="complete"
                      reportId={heroToday.id}
                      onOpen={(id) => openReport(id)}
                      meta={heroMeta}
                    />
                  </div>
                ) : null}
                {todayReports.length === 0 && !liveCard ? (
                  <EuSectionEmpty
                    message={
                      filter === "all"
                        ? "No prints today yet"
                        : "No matching prints today"
                    }
                  />
                ) : null}
                {restToday.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {restToday.map((r) => (
                      <EuReportRow
                        key={r.id}
                        report={r}
                        onOpen={(id) => openReport(id)}
                        meta={DEMO_REPORT_META[r.id]}
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
                  label="Up next · within 24 hours"
                  count={upNext.length}
                >
                  {upNext.length === 0 ? (
                    <EuSectionEmpty message="Earnings calendar wiring pending" />
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {upNext.map((u) => (
                        <EuUpNextCard key={u.id} item={u} />
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
                  label="Earlier this week"
                  count={groups.earlierThisWeek.length}
                >
                  {groups.earlierThisWeek.length === 0 ? (
                    <EuSectionEmpty
                      message={
                        filter === "all"
                          ? "No prints earlier this week"
                          : "No matching prints"
                      }
                    />
                  ) : (
                    <div className="flex flex-col gap-2">
                      {groups.earlierThisWeek.map((r) => (
                        <EuReportRow
                          key={r.id}
                          report={r}
                          onOpen={(id) => openReport(id)}
                          meta={DEMO_REPORT_META[r.id]}
                        />
                      ))}
                    </div>
                  )}
                </EuFeedSection>
              </div>

              {reports.length > 0 ? (
                <div className="mt-7 flex justify-center">
                  <button
                    type="button"
                    onClick={() => setCabinetOpen(true)}
                    className="font-mono text-[11px] tracking-[0.12em] uppercase text-[--color-text-secondary] hover:text-[--color-text-primary]"
                  >
                    View all reports →
                  </button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>

      <CoverageModal
        open={coverageOpen}
        entries={entries}
        onClose={() => setCoverageOpen(false)}
        onAdd={async (t) => {
          await add(t);
        }}
        onRemove={async (id) => {
          await remove(id);
        }}
      />

      <OnDemandReportModal
        open={onDemandOpen}
        onClose={() => setOnDemandOpen(false)}
        entries={entries}
        startReport={async (payload) => {
          setLiveCard({
            ticker: payload.ticker,
            status: "streaming",
            reportId: null,
            title: `Generating ${payload.ticker} earnings update...`,
          });
          try {
            return await startOnDemandReport(payload);
          } catch (err) {
            setLiveCard(null);
            throw err;
          }
        }}
        onReportReady={(r) => {
          setLiveCard({
            ticker: liveCard?.ticker ?? "",
            status: "complete",
            reportId: r.report_id,
            title: r.title,
          });
          void refreshReports();
        }}
      />
      {cabinetOpen ? (
        <EUCabinetView
          reports={reports}
          onBack={() => setCabinetOpen(false)}
          onOpenReport={(id) => openReport(id)}
          onDownload={(id) => downloadReport(id)}
          onRemove={async (id) => {
            await removeReport(id);
          }}
        />
      ) : null}
      {settingsOpen && config ? (
        <ReportSettingsModal
          open
          config={config}
          onClose={() => setSettingsOpen(false)}
          onSave={async (next) => {
            await saveConfig(next);
          }}
        />
      ) : null}
    </div>
  );
}
