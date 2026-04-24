import { useCallback, useState } from "react";

import type { RecentReport } from "../../api/morning-briefing";
import { MBArchiveView } from "../../components/morning-briefing/MBArchiveView";
import { MBSettingsView } from "../../components/morning-briefing/MBSettingsView";
import { OnDemandBriefingButton } from "../../components/morning-briefing/OnDemandBriefingButton";
import { useMbConfig } from "../../hooks/useMbConfig";
import { useMbReports } from "../../hooks/useMbReports";
import { useMbSchedule } from "../../hooks/useMbSchedule";

type Tab = "archive" | "settings";

export default function MorningBriefing() {
  const { config, save: saveConfig, loading: configLoading } = useMbConfig();
  const {
    schedule,
    save: saveSchedule,
    remove: removeSchedule,
  } = useMbSchedule();
  const { reports, loading: reportsLoading, refresh } = useMbReports();
  const [tab, setTab] = useState<Tab>("archive");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const onOpen = useCallback((report: RecentReport) => {
    window.open(`/reports/${report.id}`, "_blank", "noopener,noreferrer");
  }, []);

  const onReportSaved = useCallback(
    (_reportId: string) => {
      setErrorMsg(null);
      void refresh();
    },
    [refresh],
  );

  return (
    <div className="mx-auto max-w-4xl p-6 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Morning Briefings</h1>
          <p className="text-sm text-muted-foreground">
            Your daily multi-section briefing. Covers macro, markets, sectors,
            stocks, and upcoming events.
          </p>
        </div>
        <OnDemandBriefingButton
          onSaved={onReportSaved}
          onError={setErrorMsg}
        />
      </header>

      {errorMsg && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {errorMsg}
        </div>
      )}

      <div className="flex gap-2 border-b border-border">
        <button
          type="button"
          className={`px-3 py-2 text-sm ${
            tab === "archive"
              ? "border-b-2 border-primary font-medium"
              : "text-muted-foreground"
          }`}
          onClick={() => setTab("archive")}
        >
          Archive
        </button>
        <button
          type="button"
          className={`px-3 py-2 text-sm ${
            tab === "settings"
              ? "border-b-2 border-primary font-medium"
              : "text-muted-foreground"
          }`}
          onClick={() => setTab("settings")}
        >
          Settings
        </button>
      </div>

      {tab === "archive" ? (
        <MBArchiveView
          reports={reports}
          loading={reportsLoading}
          onOpen={onOpen}
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
