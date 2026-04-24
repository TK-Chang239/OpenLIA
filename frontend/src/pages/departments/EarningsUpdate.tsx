import { useCallback, useState } from "react";
import { Plus, Settings as SettingsIcon } from "lucide-react";

import {
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

export default function EarningsUpdate() {
  const { entries, add, remove } = useEuWatchlist();
  const { reports, refresh: refreshReports } = useEuReports(5);
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

  const scheduleViews: ScheduleView[] = schedules.map((s) => ({
    id: s.id,
    time: s.time,
    timezone: s.timezone,
    days_of_week: s.days_of_week,
    label: s.label,
    is_enabled: s.is_enabled,
  }));

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
        <WatchlistRow
          entries={entries}
          onAdd={async (t) => {
            await add(t);
          }}
          onRemove={async (id) => {
            await remove(id);
          }}
        />
        <div className="border-t border-[--color-border-subtle]" />
        <RecentReportsList
          reports={reports}
          onOpenReport={(id) => openReport(id)}
          onOpenCabinet={() => setCabinetOpen(true)}
        />
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
        startReport={startOnDemandReport}
        onReportReady={(r) => {
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
          onRemove={async (_id) => {
            // Report deletion endpoint arrives with a later plan.
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
