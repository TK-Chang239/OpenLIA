import { RotateCcw, Settings } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createSession } from "../../api/chat";
import { saveReportToRepo } from "../../api/repo";
import {
  fetchReport,
  reportDocxUrl,
  reportPdfUrl,
  type ReportSchema,
} from "../../api/reports";
import {
  ChatInterface,
  type InlineExtraMessage,
} from "../../components/chat/ChatInterface";
import { ReportCard } from "../../components/equity-research/ReportCard";
import { ReportSettingsModal } from "../../components/equity-research/ReportSettingsModal";
import { SuggestionChips } from "../../components/equity-research/SuggestionChips";
import { useReportStream } from "../../components/report/useReportStream";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useErConfig } from "../../hooks/useErConfig";

export default function EquityResearch() {
  const { config, loading, patch } = useErConfig();
  const [searchParams, setSearchParams] = useSearchParams();
  const tickerParam = searchParams.get("ticker");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState(tickerParam ?? "");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [subject, setSubject] = useState<string>("");
  const [schema, setSchema] = useState<ReportSchema | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [autoStarted, setAutoStarted] = useState(false);
  const fileViewer = useFileViewer();
  const {
    state: reportState,
    start: startReport,
    reset: resetReport,
    retry: retryReport,
    stop: stopReport,
  } = useReportStream();

  const dispatchReport = async (text: string) => {
    if (!config) return;
    const trimmed = text.trim();
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

  const onChipSelect = (value: string) => {
    setInput(value);
    void dispatchReport(value);
  };

  const onSend = () => {
    void dispatchReport(input);
  };

  // Phase 21: deep-link from Portfolio populates the input with ?ticker=SYM.
  // We pre-fill the textarea (already done above) and clear the query param
  // so a manual edit + send won't re-trigger on remount. Auto-dispatch is
  // intentionally NOT wired so users can adjust the prompt before sending.
  useEffect(() => {
    if (tickerParam && !autoStarted) {
      setAutoStarted(true);
      setSearchParams({}, { replace: true });
    }
  }, [tickerParam, autoStarted, setSearchParams]);

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

  const handleDownload = (id: string, fmt: "pdf" | "docx") => {
    const url = fmt === "pdf" ? reportPdfUrl(id) : reportDocxUrl(id);
    window.open(url, "_blank", "noopener");
  };

  const handleSave = async (id: string): Promise<void> => {
    await saveReportToRepo(id);
  };

  const openReport = (id: string) => {
    if (!schema) return;
    fileViewer.open({
      filename: schema.cover.title || "Report",
      kind: "pdf",
      metadata: schema.cover.subtitle ?? "",
      source: { kind: "report", reportId: id },
    });
  };

  const inline = useMemo<InlineExtraMessage[]>(() => {
    const items: InlineExtraMessage[] = [];
    if (reportState.status === "starting" || reportState.status === "writing") {
      items.push({
        after: "end",
        key: "report-progress",
        node: (
          <ReportProgressBubble
            phase={reportState.phase}
            sections={reportState.sections}
            sectionTitles={reportState.sectionTitles}
          />
        ),
      });
    }
    if (reportState.status === "error") {
      items.push({
        after: "end",
        key: "report-error",
        node: (
          <ReportErrorBubble
            message={reportState.errorMessage}
            onRetry={() => retryReport()}
          />
        ),
      });
    }
    if (
      reportState.status === "complete" &&
      schema &&
      reportState.reportId &&
      config
    ) {
      items.push({
        after: "end",
        key: `report-card-${reportState.reportId}`,
        node: (
          <div data-testid="er-report-card">
            <ReportCard
              reportId={reportState.reportId}
              mode={config.report_mode}
              subject={subject}
              companyName={null}
              createdAt={schema.generated_at ?? new Date().toISOString()}
              preview={schema.cover.tagline || schema.cover.subtitle || ""}
              onOpen={openReport}
              onDownload={handleDownload}
              onSave={handleSave}
            />
          </div>
        ),
      });
    }
    return items;
    // openReport / handleSave are stable enough for inline rendering; we
    // rely on identity-stable refs to avoid spurious chat re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportState, schema, config?.report_mode, subject]);

  if (loading || !config) {
    return <PageSkeleton />;
  }

  const active = sessionId !== null;

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
                    onSend();
                  }
                }}
                className="flex-1 rounded-xl border border-[--color-border-subtle] bg-[--color-bg-input] px-4 py-3 text-md resize-none"
              />
              <button
                type="button"
                onClick={onSend}
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
        <div className="flex-1 min-h-0">
          <ChatInterface
            sessionId={sessionId}
            greeting="Researching…"
            subtext=""
            chips={[]}
            inputPlaceholder="Ask a follow-up question about the company, sector, or report..."
            streamUrl="/api/departments/equity-research/chat"
            bodyExtras={{ session_id: sessionId }}
            extraInlineMessages={inline}
            extraIsStreaming={
              reportState.status === "starting" || reportState.status === "writing"
            }
            onExtraStop={stopReport}
          />
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

function PageSkeleton(): JSX.Element {
  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex-shrink-0 flex items-center justify-between border-b border-[--color-border-subtle] px-6">
        <div
          className="h-5 w-40 rounded bg-[--color-border-subtle] animate-pulse"
          aria-hidden="true"
        />
        <div
          className="h-8 w-32 rounded bg-[--color-border-subtle] animate-pulse"
          aria-hidden="true"
        />
      </header>
      <div className="flex-1 flex flex-col items-center justify-center gap-6 px-6">
        <div className="space-y-3 text-center">
          <div className="h-7 w-56 mx-auto rounded bg-[--color-border-subtle] animate-pulse" />
          <div className="h-4 w-72 mx-auto rounded bg-[--color-border-subtle] animate-pulse" />
        </div>
        <div className="flex flex-wrap gap-2 justify-center">
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-9 w-20 rounded-full bg-[--color-border-subtle] animate-pulse"
            />
          ))}
        </div>
      </div>
    </div>
  );
}

interface ProgressProps {
  phase: string | null;
  sections: { id: string; title: string; status: "pending" | "writing" | "done" }[];
  sectionTitles: string[];
}

function ReportProgressBubble({ phase, sections, sectionTitles }: ProgressProps): JSX.Element {
  const label =
    phase === "fetching_data"
      ? "Fetching data…"
      : phase === "writing"
        ? "Writing…"
        : phase === "finalizing"
          ? "Finalizing…"
          : "Generating…";
  const items = sections.length > 0
    ? sections
    : sectionTitles.map((t) => ({ id: t, title: t, status: "pending" as const }));
  return (
    <div
      className="rounded-[--radius-md] border border-[--color-border-subtle] p-3 text-sm text-[--color-text-secondary] max-w-[560px]"
      data-testid="report-progress"
    >
      <div className="font-medium text-[--color-text-primary]">{label}</div>
      {items.length > 0 ? (
        <ul className="mt-2 space-y-0.5 text-xs">
          {items.map((s) => (
            <li key={`${s.id}-${s.title}`} className="flex items-center gap-2">
              <span aria-hidden="true">
                {s.status === "done" ? "✓" : s.status === "writing" ? "⏳" : "•"}
              </span>
              <span>{s.title}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

interface ErrorProps {
  message: string | null;
  onRetry: () => void;
}

function ReportErrorBubble({ message, onRetry }: ErrorProps): JSX.Element {
  return (
    <div
      className="rounded-[--radius-md] border border-[--color-border-subtle] p-3 text-sm text-[--color-text-error] max-w-[560px] flex items-start gap-3"
      data-testid="report-error"
    >
      <div className="flex-1">{message ?? "Report generation failed."}</div>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1 px-2 h-7 rounded-[--radius-md] border border-[--color-border-subtle] text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
      >
        <RotateCcw size={12} /> Try again
      </button>
    </div>
  );
}
