import {
  type JSX,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";

import {
  type ChatMessage,
  createSession,
  getSession,
  listMessages,
  patchSession,
} from "../../api/chat";
import { saveReportToRepo } from "../../api/repo";
import {
  fetchReport,
  listReports,
  reportDocxUrl,
  reportPdfUrl,
  type ReportSchema,
} from "../../api/reports";
import { AssistantMessage } from "../../components/chat/AssistantMessage";
import { ErrorMessage } from "../../components/chat/ErrorMessage";
import { MessageList } from "../../components/chat/MessageList";
import { ModelPicker } from "../../components/chat/ModelPicker";
import { ThinkingIndicator } from "../../components/chat/ThinkingIndicator";
import { ToolCallChip } from "../../components/chat/ToolCallChip";
import { ToolPicker } from "../../components/chat/ToolPicker";
import { UserBubble } from "../../components/chat/UserBubble";
import { useChatStream } from "../../components/chat/useChatStream";
import { ErComposer } from "../../components/equity-research/ErComposer";
import { ReportCard } from "../../components/equity-research/ReportCard";
import { ReportProgressIndicator } from "../../components/equity-research/ReportProgressIndicator";
import { ReportSettingsModal } from "../../components/equity-research/ReportSettingsModal";
import { WelcomeStage } from "../../components/equity-research/WelcomeStage";
import { useReportStream } from "../../components/report/useReportStream";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useAuth } from "../../auth/AuthContext";
import { useChatHeaderRegistry } from "../../layouts/ChatHeaderContext";
import { useErConfig } from "../../hooks/useErConfig";

interface PersistedToolCall {
  call_id: string;
  tool_name: string;
  args_preview: string;
  status: "running" | "done" | "failed";
  summary?: string;
  structured?: Record<string, unknown> | null;
}

const DISABLED_CONNECTORS_LS_KEY = "equity-research:disabled-connector-ids";
const DISABLED_SKILLS_LS_KEY = "equity-research:disabled-skill-ids";

function readLocalStorageIds(key: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function writeLocalStorageIds(key: string, ids: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(ids));
  } catch {
    // localStorage may be disabled (private mode, quota); silently no-op.
  }
}

function firstName(displayName: string | null | undefined): string {
  if (!displayName) return "there";
  const trimmed = displayName.trim();
  if (!trimmed) return "there";
  return trimmed.split(/\s+/)[0];
}

function parseTickerCompany(
  cover: ReportSchema["cover"] | null,
): { ticker: string | null; company: string | null } {
  if (!cover) return { ticker: null, company: null };
  const title = cover.title?.trim() ?? "";
  // Patterns: "AAPL · Apple Inc.", "AAPL — Apple Inc.", "AAPL: Stock Initiation"
  const dashMatch = title.match(/^([A-Z]{1,6})\s*[·—–\-]\s*(.+)$/);
  if (dashMatch) {
    return { ticker: dashMatch[1], company: dashMatch[2].trim() };
  }
  const allCaps = title.match(/^([A-Z]{2,6})\b/);
  if (allCaps) return { ticker: allCaps[1], company: null };
  return { ticker: null, company: null };
}

export default function EquityResearch(): JSX.Element {
  const { config, patch } = useErConfig();
  const { user } = useAuth();
  const fileViewer = useFileViewer();

  const [searchParams, setSearchParams] = useSearchParams();
  const tickerParam = searchParams.get("ticker");
  const promptParam = searchParams.get("prompt");

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState(tickerParam ?? "");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string | null>(null);
  const [subject, setSubject] = useState<string>("");
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [schema, setSchema] = useState<ReportSchema | null>(null);
  const [restoredReportId, setRestoredReportId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [genStartedAt, setGenStartedAt] = useState<number | null>(null);
  const [genDurationSec, setGenDurationSec] = useState<number | null>(null);
  const [autoStarted, setAutoStarted] = useState(false);
  const [disabledConnectorIds, setDisabledConnectorIds] = useState<string[]>(
    () => readLocalStorageIds(DISABLED_CONNECTORS_LS_KEY),
  );
  const [disabledSkillIds, setDisabledSkillIds] = useState<string[]>(
    () => readLocalStorageIds(DISABLED_SKILLS_LS_KEY),
  );

  // Mirror toggle state to localStorage so it survives a page refresh.
  // The server-side session row remains the source of truth once a
  // session exists; localStorage covers the pre-session window the user
  // hits on cold load before submitting the first ticker.
  useEffect(() => {
    writeLocalStorageIds(DISABLED_CONNECTORS_LS_KEY, disabledConnectorIds);
  }, [disabledConnectorIds]);
  useEffect(() => {
    writeLocalStorageIds(DISABLED_SKILLS_LS_KEY, disabledSkillIds);
  }, [disabledSkillIds]);

  const lastSentChatRef = useRef<string>("");
  const persistedStreamRef = useRef<string | null>(null);

  const {
    state: reportState,
    start: startReport,
    reset: resetReport,
    retry: retryReport,
    stop: stopReport,
  } = useReportStream();

  const chatStream = useChatStream({
    sessionId: sessionId ?? "",
    streamUrl: "/api/departments/equity-research/chat",
    bodyExtras: useMemo(
      () => (sessionId ? { session_id: sessionId } : {}),
      [sessionId],
    ),
  });

  // Stable refs so the chat-header callbacks below don't change identity
  // on every render (chatStream is a fresh object literal each render).
  const chatStreamResetRef = useRef(chatStream.reset);
  const resetReportRef = useRef(resetReport);
  const sessionIdRef = useRef(sessionId);
  useEffect(() => {
    chatStreamResetRef.current = chatStream.reset;
    resetReportRef.current = resetReport;
    sessionIdRef.current = sessionId;
  });

  // Pre-fill from ?prompt= and clear the query so manual edits don't re-fire.
  useEffect(() => {
    if (!promptParam) return;
    setInput(promptParam);
    const next = new URLSearchParams(searchParams);
    next.delete("prompt");
    setSearchParams(next, { replace: true });
  }, [promptParam, searchParams, setSearchParams]);

  // Pre-fill from ?ticker= and clear the query (no auto-dispatch — user adjusts first).
  useEffect(() => {
    if (tickerParam && !autoStarted) {
      setAutoStarted(true);
      const next = new URLSearchParams(searchParams);
      next.delete("ticker");
      setSearchParams(next, { replace: true });
    }
  }, [tickerParam, autoStarted, searchParams, setSearchParams]);

  // Hydrate session metadata + messages whenever the session id changes.
  // Also restore the most recent report attached to this session so the
  // ReportCard reappears after returning from another conversation.
  useEffect(() => {
    if (!sessionId) {
      setHistory([]);
      setHistoryLoaded(false);
      setRestoredReportId(null);
      // Pre-session toggle state stays in React+localStorage; do not
      // reset it here, otherwise a fresh mount would clobber the
      // toggles the user picked on the prior visit.
      return;
    }
    let cancelled = false;
    setHistoryLoaded(false);
    setHistory([]);
    setRestoredReportId(null);
    persistedStreamRef.current = null;
    void Promise.all([
      getSession(sessionId).catch(() => null),
      listMessages(sessionId).catch(() => null),
      listReports({ department: "equity_research", session_id: sessionId }).catch(
        () => null,
      ),
    ]).then(async ([sess, msgs, reports]) => {
      if (cancelled) return;
      if (sess) {
        setSessionTitle(sess.title);
        setDisabledConnectorIds(sess.disabled_connector_ids ?? []);
        setDisabledSkillIds(sess.disabled_skill_ids ?? []);
      } else {
        setDisabledConnectorIds([]);
        setDisabledSkillIds([]);
      }
      setHistory(msgs?.items ?? []);
      setHistoryLoaded(true);
      const latest = reports?.items?.[0];
      if (latest) {
        try {
          const sch = await fetchReport(latest.id);
          if (cancelled) return;
          setSchema(sch);
          setRestoredReportId(latest.id);
        } catch {
          // Leave the report card hidden if the schema can't be loaded.
        }
      }
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // Snapshot streamed assistant replies into history so they persist after the
  // next send resets the live stream state.
  useEffect(() => {
    if (chatStream.state.status !== "done" && chatStream.state.status !== "stopped")
      return;
    if (chatStream.state.chunks.length === 0 && !chatStream.state.message) return;
    const key = `${chatStream.state.status}|${chatStream.state.message.length}|${chatStream.state.toolCalls.length}`;
    if (persistedStreamRef.current === key) return;
    persistedStreamRef.current = key;
    const tool_calls =
      chatStream.state.toolCalls.length > 0
        ? chatStream.state.toolCalls.map((c) => ({
            call_id: c.callId,
            tool_name: c.toolName,
            args_preview: c.argsPreview,
            status: c.status,
            summary: c.summary,
            structured: c.structured ?? null,
          }))
        : null;
    const now = new Date().toISOString();
    setHistory((prev) => [
      ...prev,
      {
        id: `streamed-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        role: "assistant",
        content: chatStream.state.message,
        tool_calls,
        model_ref: null,
        token_usage: null,
        created_at: now,
        stopped_at: chatStream.state.status === "stopped" ? now : null,
      },
    ]);
    chatStream.reset();
  }, [
    chatStream.state.status,
    chatStream.state.message,
    chatStream.state.chunks.length,
    chatStream.state.toolCalls,
    chatStream,
  ]);

  // Capture generation duration when the report stream completes.
  useEffect(() => {
    if (reportState.status !== "complete" || genStartedAt === null) return;
    if (genDurationSec !== null) return;
    setGenDurationSec((Date.now() - genStartedAt) / 1000);
  }, [reportState.status, genStartedAt, genDurationSec]);

  // Fetch the persisted schema once the server signals report.saved.
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

  const dispatchReport = useCallback(
    async (text: string, attachments?: File[]) => {
      if (!config) return;
      const trimmed = text.trim();
      if (!trimmed) return;
      setInput("");
      setStartError(null);
      setSchema(null);
      setGenDurationSec(null);
      setGenStartedAt(Date.now());
      resetReport();
      try {
        const row = await createSession({
          department: "equity_research",
          title: trimmed.slice(0, 60),
        });
        setSessionId(row.id);
        setSessionTitle(row.title);
        setSubject(trimmed);
        // Push any pre-session tool toggles onto the new row before
        // starting the report stream. Awaiting prevents the runner from
        // reading the row before the disabled lists are persisted.
        if (disabledConnectorIds.length > 0 || disabledSkillIds.length > 0) {
          try {
            await patchSession(row.id, {
              disabled_connector_ids: disabledConnectorIds,
              disabled_skill_ids: disabledSkillIds,
            });
          } catch {
            // Patch failure falls back to "all on" for this run.
          }
        }
        startReport({
          url: "/api/departments/equity-research/report",
          body: {
            mode: config.report_mode,
            user_input: trimmed,
            session_id: row.id,
          },
          attachments,
        });
      } catch (err) {
        setStartError(err instanceof Error ? err.message : "Failed to start research");
      }
    },
    [
      config,
      resetReport,
      startReport,
      disabledConnectorIds,
      disabledSkillIds,
    ],
  );

  const handleComposerSubmit = (text: string, attachments?: File[]) => {
    if (!sessionId) {
      void dispatchReport(text, attachments);
      return;
    }
    // Active-session: send a follow-up chat message.
    const trimmed = text.trim();
    if (!trimmed) return;
    lastSentChatRef.current = trimmed;
    persistedStreamRef.current = null;
    setInput("");
    const optimisticId = `optimistic-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setHistory((prev) => [
      ...prev,
      {
        id: optimisticId,
        role: "user",
        content: trimmed,
        tool_calls: null,
        model_ref: null,
        token_usage: null,
        created_at: new Date().toISOString(),
      },
    ]);
    chatStream.send(trimmed, attachments);
  };

  const handleStop = () => {
    if (
      chatStream.state.status === "opening" ||
      chatStream.state.status === "thinking" ||
      chatStream.state.status === "streaming"
    ) {
      chatStream.stop();
    }
    if (reportState.status === "starting" || reportState.status === "writing") {
      stopReport();
    }
  };

  const handleSelectSession = useCallback((id: string) => {
    if (id === sessionIdRef.current) return;
    setSessionId(id);
    setSchema(null);
    setSubject("");
    setGenDurationSec(null);
    setGenStartedAt(null);
    resetReportRef.current();
    chatStreamResetRef.current();
  }, []);

  const handleNewChat = useCallback(() => {
    setSessionId(null);
    setSessionTitle(null);
    setSchema(null);
    setSubject("");
    setHistory([]);
    setHistoryLoaded(false);
    setGenDurationSec(null);
    setGenStartedAt(null);
    setStartError(null);
    setInput("");
    resetReportRef.current();
    chatStreamResetRef.current();
  }, []);

  // Publish chat-header state to the global TopBar so the breadcrumb
  // dropdown + New Chat button render. Register on welcome state too
  // (chatTitle null hides the chat crumb, but the New Chat button stays).
  const { register, clear } = useChatHeaderRegistry();
  useEffect(() => {
    register({
      departmentId: "equity_research",
      activeSessionId: sessionId,
      chatTitle: sessionId ? sessionTitle : "New chat",
      onSelect: handleSelectSession,
      onCreate: handleNewChat,
    });
    return () => clear();
  }, [
    sessionId,
    sessionTitle,
    handleSelectSession,
    handleNewChat,
    register,
    clear,
  ]);

  const handleDownload = (id: string, fmt: "pdf" | "docx") => {
    const url = fmt === "pdf" ? reportPdfUrl(id) : reportDocxUrl(id);
    window.open(url, "_blank", "noopener");
  };

  const handleSave = async (id: string) => {
    await saveReportToRepo(id);
  };

  const openReport = (id: string) => {
    if (!schema) return;
    fileViewer.open({
      filename: schema.cover.title || "Report",
      kind: "report",
      metadata: schema.cover.subtitle ?? "",
      source: { kind: "report", reportId: id },
    });
  };

  const isReportStreaming =
    reportState.status === "starting" || reportState.status === "writing";
  const isChatStreaming =
    chatStream.state.status === "opening" ||
    chatStream.state.status === "thinking" ||
    chatStream.state.status === "streaming";
  const isStreaming = isReportStreaming || isChatStreaming;

  const autoscrollKey = useMemo(
    () =>
      `${history.length}:${chatStream.state.message.length}:${chatStream.state.toolCalls.length}:${reportState.status}:${reportState.toolCalls.length}:${schema ? "s" : "_"}`,
    [
      history.length,
      chatStream.state.message.length,
      chatStream.state.toolCalls.length,
      reportState.status,
      reportState.toolCalls.length,
      schema,
    ],
  );

  const { ticker, company } = parseTickerCompany(schema?.cover ?? null);
  const placeholder = sessionId
    ? "Ask a follow-up question about the company, sector, or report…"
    : "Enter a ticker, company, or sector (e.g., AAPL, Semiconductors)…";

  return (
    <div className="flex h-full flex-col bg-[--color-bg-base]">
      <div className="relative flex flex-1 min-h-0 flex-col">
        {!sessionId ? (
          <WelcomeStage
            firstName={firstName(user?.display_name)}
            mode={config.report_mode}
            length={config.report_length}
            onModeRowClick={() => setSettingsOpen(true)}
          />
        ) : (
          <div className="relative flex-1 min-h-0">
            <MessageList autoscrollKey={autoscrollKey}>
              {history.map((m) => (
                <HistoricalMessage key={m.id} message={m} />
              ))}

              {isReportStreaming ? (
                <>
                  <ReportProgressIndicator
                    startedAt={genStartedAt}
                    mode={config.report_mode}
                    subject={subject || sessionTitle || ""}
                  />
                  {reportState.toolCalls.length > 0 ? (
                    <div
                      data-testid="er-report-tool-chips"
                      className="flex flex-wrap gap-2"
                    >
                      {reportState.toolCalls.map((c, i) => (
                        <ToolCallChip
                          key={c.callId || `rt-${i}`}
                          toolName={c.toolName}
                          argsPreview={c.argsPreview}
                          status={c.status}
                          summary={c.summary}
                          structured={null}
                          index={i}
                        />
                      ))}
                    </div>
                  ) : null}
                </>
              ) : null}

              {reportState.status === "error" ? (
                <ErrorMessage
                  message={reportState.errorMessage ?? "Report generation failed."}
                  onRetry={() => retryReport()}
                />
              ) : null}

              {schema &&
              (reportState.status === "complete" || restoredReportId) ? (
                <div data-testid="er-report-card">
                  <ReportCard
                    reportId={reportState.reportId ?? restoredReportId ?? ""}
                    mode={config.report_mode}
                    ticker={ticker ?? null}
                    companyName={company ?? null}
                    subject={subject || sessionTitle || ""}
                    createdAt={schema.generated_at ?? new Date().toISOString()}
                    preview={schema.cover.tagline || schema.cover.subtitle || ""}
                    sectionsCount={schema.sections?.length ?? 0}
                    generatedSeconds={genDurationSec}
                    citationsCount={schema.citations?.length ?? 0}
                    onOpen={openReport}
                    onDownload={handleDownload}
                    onSave={handleSave}
                  />
                </div>
              ) : null}

              {chatStream.state.status === "thinking" ? <ThinkingIndicator /> : null}

              {chatStream.state.toolCalls.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {chatStream.state.toolCalls.map((c, i) => (
                    <ToolCallChip
                      key={c.callId}
                      toolName={c.toolName}
                      argsPreview={c.argsPreview}
                      status={c.status}
                      summary={c.summary}
                      structured={c.structured ?? null}
                      index={i}
                    />
                  ))}
                </div>
              ) : null}

              {(chatStream.state.status === "streaming" ||
                chatStream.state.status === "done" ||
                chatStream.state.status === "stopped") &&
              (chatStream.state.chunks.length > 0 || chatStream.state.message) ? (
                <AssistantMessage
                  chunks={chatStream.state.chunks}
                  streaming={chatStream.state.status === "streaming"}
                  stopped={chatStream.state.status === "stopped"}
                  flagChips={chatStream.state.flagChips}
                  skillLoads={chatStream.state.skillLoads}
                  departmentId="equity_research"
                  tokens={chatStream.state.tokens}
                  latencyMs={chatStream.state.latencyMs}
                />
              ) : null}

              {chatStream.state.status === "error" && chatStream.state.errorMessage ? (
                <ErrorMessage
                  message={chatStream.state.errorMessage}
                  onRetry={() => chatStream.send(lastSentChatRef.current)}
                />
              ) : null}

              {!historyLoaded && history.length === 0 && !isStreaming ? (
                <div className="py-6 text-center text-[12px] text-[--color-text-tertiary]">
                  Loading…
                </div>
              ) : null}
            </MessageList>
          </div>
        )}

        {startError ? (
          <p className="px-6 pb-2 text-center text-sm text-[--color-feedback-error]">
            {startError}
          </p>
        ) : null}
      </div>

      <ErComposer
        value={input}
        onChange={setInput}
        onSubmit={handleComposerSubmit}
        onStop={handleStop}
        isStreaming={isStreaming}
        placeholder={placeholder}
        mode={config.report_mode}
        length={config.report_length}
        onModeClick={() => setSettingsOpen(true)}
        modelPicker={<ModelPicker />}
        toolPicker={
          <ToolPicker
            sessionId={sessionId}
            initialDisabledConnectorIds={disabledConnectorIds}
            initialDisabledSkillIds={disabledSkillIds}
            onChange={(next) => {
              setDisabledConnectorIds(next.disabledConnectorIds);
              setDisabledSkillIds(next.disabledSkillIds);
            }}
          />
        }
        initialValue={tickerParam ?? promptParam ?? undefined}
      />

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

function HistoricalMessage({ message }: { message: ChatMessage }): JSX.Element {
  if (message.role === "user") {
    return <UserBubble content={message.content} />;
  }
  const toolCalls = (message.tool_calls as PersistedToolCall[] | null) ?? null;
  return (
    <>
      {toolCalls && toolCalls.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {toolCalls.map((c, i) => (
            <ToolCallChip
              key={c.call_id}
              toolName={c.tool_name}
              argsPreview={c.args_preview}
              status={c.status}
              summary={c.summary}
              structured={c.structured ?? null}
              index={i}
            />
          ))}
        </div>
      ) : null}
      <AssistantMessage
        content={message.content}
        streaming={false}
        departmentId="equity_research"
      />
    </>
  );
}

