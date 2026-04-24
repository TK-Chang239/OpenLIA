import { useCallback, useEffect, useState } from "react";

import { type RecentReport } from "../../api/morning-briefing";
import { fetchReport, type ReportSchema } from "../../api/reports";
import { ChatInterface } from "../../components/chat/ChatInterface";
import { ReportThumbnail } from "../../components/chat/ReportThumbnail";
import { MBArchiveView } from "../../components/morning-briefing/MBArchiveView";
import { MBSettingsView } from "../../components/morning-briefing/MBSettingsView";
import { OnDemandBriefingButton } from "../../components/morning-briefing/OnDemandBriefingButton";
import { ReportRenderer } from "../../components/report/ReportRenderer";
import { useMbChatSession } from "../../hooks/useMbChatSession";
import { useMbConfig } from "../../hooks/useMbConfig";
import { useMbReports } from "../../hooks/useMbReports";
import { useMbSchedule } from "../../hooks/useMbSchedule";

type Tab = "archive" | "chat" | "settings";

const FOLLOW_UP_CHIPS = [
  {
    label: "Summarize today's briefing",
    value: "Summarize today's Morning Briefing in 3 bullets.",
  },
  {
    label: "Biggest risks",
    value: "What are the biggest risks flagged in the latest briefing?",
  },
  {
    label: "What changed vs yesterday?",
    value:
      "What changed materially in the latest briefing compared to the previous one?",
  },
  {
    label: "Explain macro section",
    value: "Explain the macro section of the latest briefing in plain English.",
  },
];

export default function MorningBriefing() {
  const { config, save: saveConfig, loading: configLoading } = useMbConfig();
  const {
    schedule,
    save: saveSchedule,
    remove: removeSchedule,
  } = useMbSchedule();
  const { reports, loading: reportsLoading, refresh } = useMbReports();
  const { sessionId: chatSessionId } = useMbChatSession();
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

  if (viewing) {
    return (
      <div className="flex h-full" data-testid="mb-viewer">
        <div className="w-1/2 flex flex-col border-r border-border min-w-0">
          <header className="flex items-center justify-between p-3 border-b border-border gap-2">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold truncate">
                {viewing.title}
              </h2>
              <p className="text-xs text-muted-foreground">
                {new Date(viewing.created_at).toLocaleString()}
              </p>
            </div>
            <button
              type="button"
              className="text-sm text-muted-foreground hover:underline"
              onClick={closeViewer}
            >
              Close
            </button>
          </header>
          <div className="flex-1 overflow-y-auto">
            {viewingError ? (
              <div className="p-4 text-sm text-destructive">
                {viewingError}
              </div>
            ) : viewingSchema ? (
              <ReportRenderer schema={viewingSchema} />
            ) : (
              <div className="p-4 text-sm text-muted-foreground">
                Loading briefing…
              </div>
            )}
          </div>
        </div>
        <div className="w-1/2 flex flex-col min-w-0">
          <header className="p-3 border-b border-border flex items-center gap-2">
            <div className="text-sm font-semibold flex-shrink-0">
              Follow-up chat
            </div>
            <div className="min-w-0 flex-1">
              <ReportThumbnail
                reportId={viewing.id}
                filename={`${viewing.title}.pdf`}
              />
            </div>
          </header>
          <div className="flex-1 min-h-0">
            {chatSessionId ? (
              <ChatInterface
                sessionId={chatSessionId}
                greeting="Ask about this briefing"
                subtext={`Follow up on "${viewing.title}".`}
                chips={FOLLOW_UP_CHIPS}
                inputPlaceholder="Ask a follow-up about this briefing..."
              />
            ) : (
              <div className="p-4 text-sm text-muted-foreground">
                Opening chat…
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

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
        {(
          [
            { id: "archive", label: "Archive" },
            { id: "chat", label: "Chat" },
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

      {tab === "archive" ? (
        <MBArchiveView
          reports={reports}
          loading={reportsLoading}
          onOpen={onOpen}
        />
      ) : tab === "chat" ? (
        <div className="h-[600px]" data-testid="mb-chat-tab">
          {chatSessionId ? (
            <ChatInterface
              sessionId={chatSessionId}
              greeting="Morning Briefing chat"
              subtext="Ask a follow-up about any recent briefing."
              chips={FOLLOW_UP_CHIPS}
              inputPlaceholder="Ask about your Morning Briefings..."
            />
          ) : (
            <div className="text-sm text-muted-foreground">Opening chat…</div>
          )}
        </div>
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
