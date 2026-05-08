import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Archive,
  CalendarClock,
  ChevronLeft,
  Download,
  Printer,
  Settings as SettingsIcon,
  Zap,
} from "lucide-react";

import { type RecentReport } from "../../api/morning-briefing";
import { fetchReport, reportPdfUrl, type ReportSchema } from "../../api/reports";
import { MBArchiveView } from "../../components/morning-briefing/MBArchiveView";
import { MBRunNowView } from "../../components/morning-briefing/MBRunNowView";
import { MBScheduleView } from "../../components/morning-briefing/MBScheduleView";
import { MBSettingsView } from "../../components/morning-briefing/MBSettingsView";
import { ReportRenderer } from "../../components/report/ReportRenderer";
import { useMbConfig } from "../../hooks/useMbConfig";
import { useMbReports } from "../../hooks/useMbReports";
import { useMbSchedules } from "../../hooks/useMbSchedules";

type Tab = "archive" | "run" | "schedule" | "settings";

export default function MorningBriefing() {
  const navigate = useNavigate();
  const { config, save: saveConfig, loading: configLoading } = useMbConfig();
  const {
    schedules,
    loading: schedulesLoading,
    create: createSchedule,
    update: updateSchedule,
    remove: removeSchedule,
  } = useMbSchedules();
  const { reports, loading: reportsLoading, refresh } = useMbReports();
  const [tab, setTab] = useState<Tab>("archive");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [viewing, setViewing] = useState<RecentReport | null>(null);
  const [viewingSchema, setViewingSchema] = useState<ReportSchema | null>(null);
  const [viewingError, setViewingError] = useState<string | null>(null);

  const onOpen = useCallback((report: RecentReport) => {
    setViewing(report);
    setViewingSchema(null);
    setViewingError(null);
  }, []);

  const closeViewer = useCallback(() => {
    setViewing(null);
    setViewingSchema(null);
    setViewingError(null);
  }, []);

  useEffect(() => {
    if (!viewing) return;
    let cancelled = false;
    fetchReport(viewing.id)
      .then((s) => {
        if (!cancelled) setViewingSchema(s);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setViewingError(
            err instanceof Error ? err.message : "Failed to load briefing",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [viewing]);

  const onReportSaved = useCallback(
    (_reportId: string) => {
      setErrorMsg(null);
      void refresh();
    },
    [refresh],
  );

  const openReportById = useCallback(
    async (reportId: string) => {
      const match = reports.find((r) => r.id === reportId);
      if (match) {
        onOpen(match);
        return;
      }
      // Newly saved report — refresh the list, then try opening from the fresh list.
      await refresh();
      onOpen({
        id: reportId,
        title: "Morning Briefing",
        report_type: "morning_briefing",
        created_at: new Date().toISOString(),
      });
    },
    [reports, refresh, onOpen],
  );

  const askInSecretary = useCallback(() => {
    if (!viewing) return;
    navigate(`/secretary?attached_report=${encodeURIComponent(viewing.id)}`);
  }, [navigate, viewing]);

  const archiveCount = useMemo(() => reports.length, [reports.length]);

  if (viewing) {
    return (
      <div
        className="flex flex-col h-full animate-mb-report-enter"
        data-testid="mb-viewer"
      >
        <header
          className="h-[52px] flex items-center gap-2.5 px-6 flex-shrink-0 border-b sticky top-0 bg-[--color-bg-base] z-10 animate-mb-report-header-enter"
          style={{ borderColor: "var(--color-border-subtle)" }}
        >
          <button
            type="button"
            onClick={closeViewer}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
            style={{ borderColor: "var(--color-border-secondary)" }}
          >
            <ChevronLeft size={14} />
            Close
          </button>
          <span
            className="ml-3 font-mono text-[10px] tracking-[0.1em] uppercase truncate"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            Report ·{" "}
            <strong className="text-[--color-text-primary] font-medium">
              {viewing.title}
            </strong>{" "}
            · {new Date(viewing.created_at).toLocaleString()}
          </span>
          <div className="flex-1" />
          <a
            href={reportPdfUrl(viewing.id)}
            download={`${viewing.title}.pdf`}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
            style={{ borderColor: "var(--color-border-secondary)" }}
            data-testid="mb-viewer-download"
          >
            <Download size={13} />
            Download
          </a>
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
            style={{ borderColor: "var(--color-border-secondary)" }}
          >
            <Printer size={13} />
            Print
          </button>
          <button
            type="button"
            onClick={askInSecretary}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
            style={{ borderColor: "var(--color-border-secondary)" }}
            data-testid="mb-ask-in-secretary"
          >
            Ask in Secretary →
          </button>
        </header>
        <div className="flex-1 overflow-y-auto animate-mb-report-body-enter">
          {viewingError ? (
            <div
              key="err"
              className="p-6 text-sm text-[--color-feedback-error] animate-mb-report-content-enter"
            >
              {viewingError}
            </div>
          ) : viewingSchema ? (
            <div key="ok" className="animate-mb-report-content-enter">
              <ReportRenderer schema={viewingSchema} />
            </div>
          ) : (
            <div
              key="load"
              className="p-6 text-sm text-[--color-text-tertiary] animate-mb-report-content-enter"
            >
              Loading briefing…
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <header
        className="h-14 flex items-center gap-3.5 px-6 flex-shrink-0 border-b"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <h1 className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
          Morning Briefings
        </h1>
        <span
          className="ml-3.5 pl-3.5 font-mono text-[10px] tracking-[0.1em] uppercase border-l"
          style={{
            borderColor: "var(--color-border-subtle)",
            color: "var(--color-text-tertiary)",
          }}
        >
          Department ·{" "}
          <strong
            className="font-medium"
            style={{ color: "var(--color-feedback-success)" }}
          >
            Active
          </strong>
        </span>
        <div className="flex-1" />
      </header>

      <nav
        className="h-11 flex items-stretch px-6 flex-shrink-0 border-b gap-1"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <TabButton
          active={tab === "archive"}
          onClick={() => setTab("archive")}
          icon={<Archive size={14} />}
          label="Archive"
          badge={archiveCount}
        />
        <TabButton
          active={tab === "schedule"}
          onClick={() => setTab("schedule")}
          icon={<CalendarClock size={14} />}
          label="Schedule"
        />
        <TabButton
          active={tab === "settings"}
          onClick={() => setTab("settings")}
          icon={<SettingsIcon size={14} />}
          label="Settings"
        />
        <div className="flex-1" aria-hidden="true" />
        <TabButton
          active={tab === "run"}
          onClick={() => setTab("run")}
          icon={<Zap size={14} />}
          label="Run Now"
        />
      </nav>

      {errorMsg && (
        <div
          className="mx-6 mt-3 rounded-md border p-3 text-sm"
          style={{
            borderColor: "var(--color-feedback-error)",
            color: "var(--color-feedback-error)",
            background: "var(--color-bg-base)",
          }}
        >
          {errorMsg}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        <div key={tab} className="animate-mb-tab-enter">
          {tab === "archive" ? (
            <MBArchiveView
              reports={reports}
              loading={reportsLoading}
              schedules={schedules}
              onOpen={onOpen}
              onGoToSettings={() => setTab("settings")}
            />
          ) : tab === "run" ? (
            configLoading || !config ? (
              <div className="text-sm text-[--color-text-tertiary] p-8">
                Loading…
              </div>
            ) : (
              <MBRunNowView
                baseConfig={config}
                onError={setErrorMsg}
                onReportSaved={onReportSaved}
                onOpenReport={(id) => void openReportById(id)}
              />
            )
          ) : tab === "schedule" ? (
            <MBScheduleView
              schedules={schedules}
              loading={schedulesLoading}
              onCreateSchedule={createSchedule}
              onUpdateSchedule={updateSchedule}
              onRemoveSchedule={removeSchedule}
            />
          ) : configLoading || !config ? (
            <div className="text-sm text-[--color-text-tertiary] p-8">
              Loading settings…
            </div>
          ) : (
            <MBSettingsView
              config={config}
              onSaveConfig={saveConfig}
              onError={setErrorMsg}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="group relative inline-flex items-center gap-2 px-3.5 h-full bg-transparent border-0 text-[13.5px] cursor-pointer transition-all duration-[--duration-normal] hover:bg-[--color-surface-hover]"
      style={{
        color: active
          ? "var(--color-text-primary)"
          : "var(--color-text-secondary)",
        fontWeight: active ? 500 : undefined,
      }}
    >
      <span
        aria-hidden="true"
        className="inline-flex transition-transform duration-[--duration-normal] group-hover:-translate-y-px"
      >
        {icon}
      </span>
      <span>{label}</span>
      {typeof badge === "number" ? (
        <span
          aria-hidden="true"
          className="font-mono text-[10px] tracking-[0.04em] px-1.5 py-px rounded-full transition-colors duration-[--duration-normal]"
          style={{
            background: active
              ? "var(--color-accent-primary)"
              : "var(--color-surface-active)",
            color: active
              ? "var(--color-accent-on)"
              : "var(--color-text-secondary)",
          }}
        >
          {badge}
        </span>
      ) : null}
      {active ? (
        <span
          aria-hidden="true"
          className="absolute left-0 right-0 -bottom-px h-0.5 origin-center animate-mb-tab-underline"
          style={{ background: "var(--color-text-primary)" }}
        />
      ) : null}
    </button>
  );
}
