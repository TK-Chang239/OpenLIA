import { Settings } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { createSession } from "../../api/chat";
import { fetchReport, reportPdfUrl, type ReportSchema } from "../../api/reports";
import { ChatInterface } from "../../components/chat/ChatInterface";
import { ReportCard } from "../../components/equity-research/ReportCard";
import { ReportSettingsModal } from "../../components/equity-research/ReportSettingsModal";
import { SuggestionChips } from "../../components/equity-research/SuggestionChips";
import { ReportRenderer } from "../../components/report/ReportRenderer";
import { useReportStream } from "../../components/report/useReportStream";
import { useErConfig } from "../../hooks/useErConfig";

export default function EquityResearch() {
  const { config, loading, patch } = useErConfig();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [subject, setSubject] = useState<string>("");
  const [schema, setSchema] = useState<ReportSchema | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const { state: reportState, start: startReport, reset: resetReport } = useReportStream();

  const onChipSelect = (value: string) => {
    setInput(value);
    inputRef.current?.focus();
  };

  const onSend = async () => {
    if (!config) return;
    const trimmed = input.trim();
    if (!trimmed) return;
    setInput("");
    setStartError(null);
    setSchema(null);
    resetReport();
    try {
      const row = await createSession({
        department: "equity_research",
        title: trimmed.slice(0, 60),
      });
      setSessionId(row.id);
      setSubject(trimmed);
      startReport({
        url: "/api/departments/equity-research/report",
        body: {
          mode: config.report_mode,
          user_input: trimmed,
          session_id: row.id,
        },
      });
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Failed to start research");
    }
  };

  // Fetch the persisted schema once the server signals `report.saved`.
  useEffect(() => {
    if (reportState.status !== "complete" || !reportState.reportId) return;
    if (schema?.department === "equity_research" && schema) return;
    let cancelled = false;
    void fetchReport(reportState.reportId)
      .then((s) => {
        if (!cancelled) setSchema(s);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setStartError(err instanceof Error ? err.message : "Failed to load report");
      });
    return () => {
      cancelled = true;
    };
  }, [reportState.status, reportState.reportId, schema]);

  if (loading || !config) {
    return <div className="p-6 text-sm text-[--color-text-tertiary]">Loading…</div>;
  }

  const active = sessionId !== null;

  const downloadPdf = (id: string) => {
    window.open(reportPdfUrl(id), "_blank", "noopener");
  };

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex-shrink-0 flex items-center justify-between border-b border-[--color-border-subtle] px-6">
        <h1 className="text-xl font-semibold">Equity Research</h1>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className="inline-flex items-center gap-2 h-8 px-3 text-sm border border-[--color-border-secondary] rounded-[--radius-md] text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        >
          <Settings size={16} /> Report Settings
        </button>
      </header>

      {!active && (
        <>
          <div className="flex-1 flex flex-col items-center justify-center gap-6 px-6">
            <div className="text-center">
              <h2 className="text-2xl font-semibold">Equity Research</h2>
              <p className="mt-2 text-md text-[--color-text-secondary]">
                Research companies, sectors, and market trends
              </p>
            </div>
            <SuggestionChips onSelect={onChipSelect} />
            {startError ? (
              <p className="text-sm text-[--color-text-error]">{startError}</p>
            ) : null}
          </div>

          <div className="flex-shrink-0 px-6 py-4 border-t border-[--color-border-subtle]">
            <div className="max-w-[680px] mx-auto flex items-end gap-2">
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                placeholder="Enter a ticker, company, or sector (e.g., AAPL, Semiconductors)..."
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void onSend();
                  }
                }}
                className="flex-1 rounded-xl border border-[--color-border-subtle] bg-[--color-bg-input] px-4 py-3 text-md resize-none"
              />
              <button
                type="button"
                onClick={() => void onSend()}
                disabled={!input.trim()}
                aria-label="Send"
                className="w-8 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white disabled:opacity-40 flex items-center justify-center"
              >
                <SendArrow />
              </button>
            </div>
          </div>
        </>
      )}

      {active && sessionId && (
        <div className="flex flex-1 min-h-0">
          <div className="w-[360px] flex-shrink-0 border-r border-[--color-border-subtle] overflow-y-auto p-4 space-y-3">
            <ReportStatusPanel
              status={reportState.status}
              phase={reportState.phase}
              sectionTitles={reportState.sectionTitles}
              errorMessage={reportState.errorMessage}
            />
            {schema && reportState.reportId ? (
              <ReportCard
                reportId={reportState.reportId}
                mode={config.report_mode}
                subject={subject}
                companyName={null}
                createdAt={schema.generated_at ?? new Date().toISOString()}
                preview={schema.cover.tagline || schema.cover.subtitle || ""}
                onOpen={() => setViewerOpen(true)}
                onDownload={(id) => downloadPdf(id)}
                onSave={() => {
                  /* Save-to-repo handled by Phase 12 SaveToRepoButton inside the viewer. */
                }}
              />
            ) : null}
          </div>
          <div className="flex-1 min-w-0">
            {viewerOpen && schema ? (
              <div className="h-full flex flex-col">
                <div className="flex items-center justify-between border-b border-[--color-border-subtle] px-4 py-2">
                  <h2 className="text-sm font-medium">{schema.cover.title}</h2>
                  <button
                    type="button"
                    onClick={() => setViewerOpen(false)}
                    className="text-sm text-[--color-text-secondary]"
                  >
                    Close
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto">
                  <ReportRenderer schema={schema} />
                </div>
              </div>
            ) : (
              <ChatInterface
                sessionId={sessionId}
                greeting="Researching…"
                subtext=""
                chips={[]}
                inputPlaceholder="Ask a follow-up question about the company, sector, or report..."
              />
            )}
          </div>
        </div>
      )}

      <ReportSettingsModal
        open={settingsOpen}
        config={config}
        onClose={() => setSettingsOpen(false)}
        onSave={async (p) => {
          await patch(p);
        }}
      />
    </div>
  );
}

function SendArrow(): JSX.Element {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 19V5M5 12l7-7 7 7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface PanelProps {
  status: string;
  phase: string | null;
  sectionTitles: string[];
  errorMessage: string | null;
}

function ReportStatusPanel({ status, phase, sectionTitles, errorMessage }: PanelProps): JSX.Element {
  if (status === "error") {
    return (
      <div className="rounded-[--radius-md] border border-[--color-border-subtle] p-3 text-sm text-[--color-text-error]">
        {errorMessage ?? "Report generation failed."}
      </div>
    );
  }
  if (status === "complete") {
    return (
      <div className="rounded-[--radius-md] border border-[--color-border-subtle] p-3 text-sm text-[--color-text-secondary]">
        Report ready.
      </div>
    );
  }
  const label =
    status === "starting"
      ? "Starting…"
      : phase === "fetching_data"
        ? "Fetching data…"
        : phase === "writing"
          ? "Writing…"
          : phase === "finalizing"
            ? "Finalizing…"
            : "Generating…";
  return (
    <div className="rounded-[--radius-md] border border-[--color-border-subtle] p-3 text-sm text-[--color-text-secondary]">
      <div className="font-medium text-[--color-text-primary]">{label}</div>
      {sectionTitles.length > 0 ? (
        <ul className="mt-2 list-disc list-inside space-y-0.5 text-xs">
          {sectionTitles.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
