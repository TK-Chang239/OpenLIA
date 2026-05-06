import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { type RecentReport } from "../../api/morning-briefing";
import { fetchReport, reportPdfUrl, type ReportSchema } from "../../api/reports";
import { MBArchiveView } from "../../components/morning-briefing/MBArchiveView";
import { MBSettingsView } from "../../components/morning-briefing/MBSettingsView";
import { ModelPicker } from "../../components/morning-briefing/ModelPicker";
import { OnDemandBriefingButton } from "../../components/morning-briefing/OnDemandBriefingButton";
import { ReportRenderer } from "../../components/report/ReportRenderer";
import { useMbConfig } from "../../hooks/useMbConfig";
import { useMbReports } from "../../hooks/useMbReports";
import { useMbSchedule } from "../../hooks/useMbSchedule";

type Tab = "archive" | "settings";

export default function MorningBriefing() {
  const navigate = useNavigate();
  const { config, save: saveConfig, loading: configLoading } = useMbConfig();
  const {
    schedule,
    save: saveSchedule,
    remove: removeSchedule,
  } = useMbSchedule();
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

  const askInSecretary = useCallback(() => {
    if (!viewing) return;
    navigate(`/secretary?attached_report=${encodeURIComponent(viewing.id)}`);
  }, [navigate, viewing]);

  if (viewing) {
    return (
      <div
        className="mx-auto max-w-7xl p-6 space-y-4 h-full flex flex-col"
        data-testid="mb-viewer"
      >
        <header className="flex items-center justify-between gap-3 flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold truncate">{viewing.title}</h2>
            <p className="text-xs text-muted-foreground">
              {new Date(viewing.created_at).toLocaleString()}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <a
              href={reportPdfUrl(viewing.id)}
              download={`${viewing.title}.pdf`}
              className="text-sm border border-border-subtle rounded-md px-3 py-1.5 hover:bg-surface-hover"
              data-testid="mb-viewer-download"
            >
              ↓ Download
            </a>
            <button
              type="button"
              onClick={askInSecretary}
              className="text-sm border border-border-subtle rounded-md px-3 py-1.5 hover:bg-surface-hover"
              data-testid="mb-ask-in-secretary"
            >
              Ask in Secretary →
            </button>
            <button
              type="button"
              className="text-sm text-muted-foreground hover:underline"
              onClick={closeViewer}
            >
              Close
            </button>
          </div>
        </header>
        <div className="flex-1 overflow-y-auto">
          {viewingError ? (
            <div className="p-4 text-sm text-destructive">{viewingError}</div>
          ) : viewingSchema ? (
            <ReportRenderer schema={viewingSchema} />
          ) : (
            <div className="p-4 text-sm text-muted-foreground">
              Loading briefing…
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl p-6 space-y-6">
      <header
        className="h-14 flex items-center justify-between flex-shrink-0"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold truncate">Morning Briefings</h1>
        </div>
        <div className="flex items-center gap-2">
          <ModelPicker
            departmentSlug="morning-briefing"
            onError={setErrorMsg}
          />
          <OnDemandBriefingButton
            onSaved={onReportSaved}
            onError={setErrorMsg}
          />
          <button
            type="button"
            onClick={() => setTab("settings")}
            className="text-sm underline"
            data-testid="mb-header-settings"
          >
            {"⚙ Settings"}
          </button>
        </div>
      </header>

      {errorMsg && (
        <div
          className="rounded-[var(--radius-lg,0.5rem)] border p-3 text-sm"
          style={{
            borderColor: "var(--color-feedback-error)",
            color: "var(--color-feedback-error)",
            background: "var(--color-bg-base)",
          }}
        >
          {errorMsg}
        </div>
      )}

      <div
        className="flex gap-2 border-b"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        {(
          [
            { id: "archive", label: "Archive" },
            { id: "settings", label: "Settings" },
          ] as { id: Tab; label: string }[]
        ).map((t) => (
          <button
            key={t.id}
            type="button"
            className={`px-3 py-2 text-sm ${
              tab === t.id
                ? "border-b-2 border-primary font-medium"
                : "text-muted-foreground"
            }`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "settings" && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setTab("archive")}
            className="text-sm underline"
            data-testid="mb-settings-back"
          >
            {"← Back to Reports"}
          </button>
          <span className="text-sm font-medium">
            Morning Briefings Settings
          </span>
        </div>
      )}

      {tab === "archive" ? (
        <MBArchiveView
          reports={reports}
          loading={reportsLoading}
          onOpen={onOpen}
          onGoToSettings={() => setTab("settings")}
        />
      ) : configLoading || !config ? (
        <div className="text-sm text-muted-foreground">Loading settings…</div>
      ) : (
        <MBSettingsView
          config={config}
          schedule={schedule}
          onSaveConfig={saveConfig}
          onSaveSchedule={saveSchedule}
          onRemoveSchedule={removeSchedule}
        />
      )}
    </div>
  );
}
