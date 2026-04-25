import { useCallback, useState } from "react";
import { Plus, Settings as SettingsIcon } from "lucide-react";

import {
  deleteReport,
  startOnDemandReport,
  type EuScheduleCreate,
  type EuScheduleUpdate,
  type RecentReport,
} from "../../api/earnings-update";
import { EUCabinetView } from "../../components/earnings-update/EUCabinetView";
import { OnDemandReportModal } from "../../components/earnings-update/OnDemandReportModal";
import { RecentReportsList } from "../../components/earnings-update/RecentReportsList";
import { ReportSettingsModal } from "../../components/earnings-update/ReportSettingsModal";
import {
  ScheduleManager,
  type ScheduleView,
} from "../../components/earnings-update/ScheduleManager";
import { type Day, type SchedulePayload } from "../../components/earnings-update/AddScheduleModal";
import { WatchlistRow } from "../../components/earnings-update/WatchlistRow";
import { downloadUrlForReport } from "../../api/files";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useEuConfig } from "../../hooks/useEuConfig";
import { useEuReports } from "../../hooks/useEuReports";
import { useEuSchedules } from "../../hooks/useEuSchedules";
import { useEuWatchlist } from "../../hooks/useEuWatchlist";

const DAY_TO_NUM: Record<Day, number> = {
  sun: 0,
  mon: 1,
  tue: 2,
  wed: 3,
  thu: 4,
  fri: 5,
  sat: 6,
};

function payloadToCreate(p: SchedulePayload): EuScheduleCreate {
  return {
    time: p.time,
    timezone: p.timezone,
    days_of_week: p.days_of_week.map((d) => DAY_TO_NUM[d]),
    label: p.label ? p.label : null,
    is_enabled: true,
  };
}

function payloadToUpdate(
  p: SchedulePayload & { is_enabled: boolean },
): EuScheduleUpdate {
  return {
    time: p.time,
    timezone: p.timezone,
    days_of_week: p.days_of_week.map((d) => DAY_TO_NUM[d]),
    label: p.label ? p.label : null,
    is_enabled: p.is_enabled,
  };
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
  } = useEuReports(5);
  const {
    schedules,
    create: createSchedule,
    update: updateSchedule,
    remove: removeSchedule,
  } = useEuSchedules();
  const { config, save: saveConfig } = useEuConfig();

  const [cabinetOpen, setCabinetOpen] = useState(false);
  const [onDemandOpen, setOnDemandOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [generatingTicker, setGeneratingTicker] = useState<string | null>(null);

  const fv = useFileViewer();

  const openReport = useCallback(
    (id: string, fallback?: RecentReport) => {
      const match = fallback ?? findReport(reports, id);
      fv.open({
        filename: match?.title ?? "Earnings Update",
        kind: "markdown",
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

  const scheduleViews: ScheduleView[] = schedules.map((s) => ({
    id: s.id,
    time: s.time,
    timezone: s.timezone,
    days_of_week: s.days_of_week,
    label: s.label,
    is_enabled: s.is_enabled,
  }));

  const hasError = Boolean(watchlistError || reportsError);

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex items-center justify-between border-b border-[--color-border-subtle] px-6 flex-shrink-0">
        <h1 className="text-xl font-semibold">Earnings Updates</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Report settings"
            className="text-[--color-text-secondary] hover:text-[--color-text-primary] p-1"
          >
            <SettingsIcon size={18} />
          </button>
          <button
            type="button"
            onClick={() => setOnDemandOpen(true)}
            className="flex items-center gap-1 bg-[--color-accent-primary] text-white text-sm px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover]"
          >
            <Plus size={16} /> On-Demand Report
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        {hasError ? (
          <div
            role="alert"
            className="mx-6 mt-4 flex items-center justify-between gap-4 border border-[--color-feedback-error] rounded-[--radius-md] px-4 py-2 text-sm text-[--color-feedback-error]"
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

        {watchlistLoading ? (
          <section>
            <header className="flex items-center justify-between px-6 pt-5 pb-3">
              <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
                Watchlist
              </h3>
            </header>
            <div className="flex gap-3 px-6 pb-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="w-[148px] h-[120px]" />
              ))}
            </div>
          </section>
        ) : (
          <WatchlistRow
            entries={entries}
            onAdd={async (t) => {
              await add(t);
            }}
            onRemove={async (id) => {
              await remove(id);
            }}
          />
        )}
        <div className="border-t border-[--color-border-subtle]" />

        {generatingTicker ? (
          <div
            data-testid="eu-generating"
            className="mx-6 mt-4 flex items-center gap-3 border border-[--color-border-subtle] bg-[--color-surface-hover] rounded-[--radius-md] px-4 py-2 text-sm"
          >
            <span
              aria-hidden
              className="inline-block w-2 h-2 rounded-full bg-[--color-accent-primary] animate-pulse"
            />
            <span>Generating report for {generatingTicker}...</span>
          </div>
        ) : null}

        {reportsLoading ? (
          <section>
            <header className="flex items-center justify-between px-6 pt-5 pb-3">
              <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
                Recent Reports
              </h3>
            </header>
            <div className="px-6 pb-4 flex flex-col gap-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          </section>
        ) : (
          <RecentReportsList
            reports={reports}
            onOpenReport={(id) => openReport(id)}
            onOpenCabinet={() => setCabinetOpen(true)}
          />
        )}
        <div className="border-t border-[--color-border-subtle]" />
        <ScheduleManager
          schedules={scheduleViews}
          onCreate={(p) => createSchedule(payloadToCreate(p))}
          onUpdate={(id, p) => updateSchedule(id, payloadToUpdate(p))}
          onRemove={(id) => removeSchedule(id)}
        />
      </div>

      <OnDemandReportModal
        open={onDemandOpen}
        onClose={() => setOnDemandOpen(false)}
        entries={entries}
        startReport={async (payload) => {
          setGeneratingTicker(payload.ticker);
          try {
            return await startOnDemandReport(payload);
          } catch (err) {
            setGeneratingTicker(null);
            throw err;
          }
        }}
        onReportReady={(r) => {
          setGeneratingTicker(null);
          void refreshReports();
          openReport(r.report_id, {
            id: r.report_id,
            title: r.title,
            subject: null,
            report_type: "earnings_analysis",
            created_at: new Date().toISOString(),
          });
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
