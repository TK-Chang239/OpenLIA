import {
  type JSX,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  type ChatMessage,
  createSession,
  getSession,
  listMessages,
  patchSession,
} from "../../api/chat";
import {
  type CapabilityManifest,
  fetchCapabilities,
} from "../../api/capabilities";
import { saveReportToRepo, unsaveFromRepo } from "../../api/repo";
import {
  deleteReport,
  fetchReport,
  listReports,
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
import { CapabilitySidebar } from "../../components/equity-research/CapabilitySidebar/CapabilitySidebar";
import { ClarifierModal } from "../../components/equity-research/ClarifierModal/ClarifierModal";
import { ErComposer } from "../../components/equity-research/ErComposer";
import { FrameworkTemplatePicker } from "../../components/equity-research/FrameworkTemplatePicker";
import { ReportCard } from "../../components/equity-research/ReportCard";
import { ReportProgressIndicator } from "../../components/equity-research/ReportProgressIndicator";
import { ReportSettingsModal } from "../../components/equity-research/ReportSettingsModal";
import { WelcomeStage } from "../../components/equity-research/WelcomeStage";
import {
  useReportStream,
  useReportStreamAttach,
} from "../../components/report/useReportStream";
import { useV2ReportStream } from "../../components/report/useV2ReportStream";
import { useFileViewer } from "../../components/viewer/FileViewerContext";
import { useToast } from "../../components/primitives/Toast";
import { useAuth } from "../../auth/AuthContext";
import { useChatHeaderRegistry } from "../../layouts/ChatHeaderContext";
import { useErConfig } from "../../hooks/useErConfig";

const CHAT_FOLLOWUP_INTRO_TOAST_KEY = "chat_followup_intro_toast_seen";

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
const ENGINE_V2_LS_KEY = "equity-research:engine-v2-enabled";

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
  const toast = useToast();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [searchParams, setSearchParams] = useSearchParams();
  const tickerParam = searchParams.get("ticker");
  const promptParam = searchParams.get("prompt");
  const reportIdParam = searchParams.get("report_id");

  // Reattach to an in-progress (or completed) background report via ?report_id.
  useReportStreamAttach(reportIdParam);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState(tickerParam ?? "");
  const [frameworkTemplateId, setFrameworkTemplateId] = useState<string | null>(
    () => {
      try {
        return (
          window.localStorage.getItem("er.frameworkTemplateId") || null
        );
      } catch {
        return null;
      }
    },
  );
  useEffect(() => {
    try {
      if (frameworkTemplateId) {
        window.localStorage.setItem("er.frameworkTemplateId", frameworkTemplateId);
      } else {
        window.localStorage.removeItem("er.frameworkTemplateId");
      }
    } catch {
      /* localStorage disabled */
    }
  }, [frameworkTemplateId]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string | null>(null);
  const [subject, setSubject] = useState<string>("");
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [schema, setSchema] = useState<ReportSchema | null>(null);
  const [restoredExpiredAt, setRestoredExpiredAt] = useState<string | null>(null);
  const [restoredTombstone, setRestoredTombstone] = useState<{
    title: string;
    createdAt: string;
  } | null>(null);
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
  // Force cache refresh: when true, the next report dispatch bypasses
  // the cached document store. Ephemeral (one-shot per run); the
  // ReportSettingsModal surfaces the toggle.
  const [forceCacheRefresh, setForceCacheRefresh] = useState(false);
  const [capabilityManifest, setCapabilityManifest] =
    useState<CapabilityManifest | null>(null);
  const [engineV2Enabled, setEngineV2EnabledState] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem(ENGINE_V2_LS_KEY) === "1";
    } catch {
      return false;
    }
  });
  const setEngineV2Enabled = useCallback((next: boolean) => {
    setEngineV2EnabledState(next);
    try {
      if (next) window.localStorage.setItem(ENGINE_V2_LS_KEY, "1");
      else window.localStorage.removeItem(ENGINE_V2_LS_KEY);
    } catch {
      // localStorage may be disabled; no-op.
    }
  }, []);

  const v2Stream = useV2ReportStream();

  // Lazy-load the v2.2 capability manifest the first time the welcome
  // view shows. Network failures degrade silently — the sidebar simply
  // stays hidden.
  useEffect(() => {
    if (sessionId || capabilityManifest) return;
    let cancelled = false;
    void fetchCapabilities()
      .then((m) => {
        if (!cancelled) setCapabilityManifest(m);
      })
      .catch(() => {
        // Endpoint may not exist on older deployments; stay quiet.
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, capabilityManifest]);

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

  // Re-anchor the report card when the server re-attaches a new report to this
  // session (e.g. after a revision). The event is fired by AppLayout's
  // NotificationsWatcher via the useNotificationsStream hook.
  useEffect(() => {
    const handler = (e: Event) => {
      const { session_id, new_report_id } = (e as CustomEvent<{ session_id: string; new_report_id: string }>).detail;
      if (session_id !== sessionIdRef.current) return;
      setRestoredReportId(new_report_id);
      setRestoredExpiredAt(null);
      setRestoredTombstone(null);
      void fetchReport(new_report_id)
        .then((s) => setSchema(s))
        .catch(() => {/* leave existing card if re-fetch fails */});
    };
    window.addEventListener("openlia:attached_report_changed", handler);
    return () => window.removeEventListener("openlia:attached_report_changed", handler);
  }, []);

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
      setRestoredExpiredAt(null);
      setRestoredTombstone(null);
      // Pre-session toggle state stays in React+localStorage; do not
      // reset it here, otherwise a fresh mount would clobber the
      // toggles the user picked on the prior visit.
      return;
    }
    let cancelled = false;
    setHistoryLoaded(false);
    setHistory([]);
    setRestoredReportId(null);
    setRestoredExpiredAt(null);
    setRestoredTombstone(null);
    persistedStreamRef.current = null;
    void Promise.all([
      getSession(sessionId).catch(() => null),
      listMessages(sessionId).catch(() => null),
      // include_expired=true so a tombstoned report's metadata still
      // surfaces here — the ReportCard renders a "no longer available"
      // anchor in conversation history without breaking the chat flow.
      listReports({
        department: "equity_research",
        session_id: sessionId,
        include_expired: true,
      }).catch(() => null),
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
        if (latest.expired_at) {
          // Tombstone: skip fetchReport (no schema to load).
          setRestoredReportId(latest.id);
          setRestoredExpiredAt(latest.expired_at);
          setRestoredTombstone({ title: latest.title, createdAt: latest.created_at });
          return;
        }
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

  // Persist report_id into the URL so a page reload can reattach via
  // useReportStreamAttach. Only writes when a fresh generation completes
  // (i.e. ?report_id is not already in the URL from a prior reattach).
  useEffect(() => {
    if (reportState.status !== "complete" || !reportState.reportId) return;
    if (reportIdParam === reportState.reportId) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("report_id", reportState.reportId!);
        return next;
      },
      { replace: true },
    );
  }, [reportState.status, reportState.reportId, reportIdParam, setSearchParams]);

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
          setStartError(err instanceof Error ? err.message : t("equity_research.report_load_failed"));
      });
    return () => {
      cancelled = true;
    };
  }, [reportState.status, reportState.reportId, schema, t]);

  // Implicit-binding one-time intro toast: fires on the first report.saved
  // the user sees, then never again (localStorage flag).
  useEffect(() => {
    if (reportState.status !== "complete" || !reportState.reportId) return;
    if (localStorage.getItem(CHAT_FOLLOWUP_INTRO_TOAST_KEY) === "1") return;
    localStorage.setItem(CHAT_FOLLOWUP_INTRO_TOAST_KEY, "1");
    toast.push({
      title: t("equity_research.report_linked_toast"),
      tone: "info",
      durationMs: 6000,
    });
  }, [reportState.status, reportState.reportId, toast, t]);

  // Redirect toast: fired when the backend signals this report was generated
  // in a new session because the current session was already bound.
  // The redirect_session_id is passed via dispatchReport's return value when
  // the background-generate endpoint is used (redirect=true path).
  const [redirectSessionId, setRedirectSessionId] = useState<string | null>(null);
  useEffect(() => {
    if (!redirectSessionId) return;
    const targetId = redirectSessionId;
    setRedirectSessionId(null);
    toast.push({
      title: t("equity_research.new_thread_toast"),
      tone: "info",
      durationMs: 8000,
      undo: {
        label: t("equity_research.open_toast"),
        onClick: () => {
          void navigate(`/chat/${targetId}`);
        },
      },
    });
  }, [redirectSessionId, toast, navigate, t]);

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
        if (engineV2Enabled && frameworkTemplateId) {
          // v2.2 engine path: POST to the v2 SSE endpoint. ClarifierModal
          // renders when the run pauses on blocking warnings.
          v2Stream.start({
            url: "/api/departments/equity-research/v2/report",
            body: {
              user_input: trimmed,
              session_id: row.id,
              report_template_id: frameworkTemplateId,
              composer_inputs: {
                ...(forceCacheRefresh ? { force_cache_refresh: true } : {}),
              },
            },
          });
        } else {
          startReport({
            url: "/api/departments/equity-research/report",
            body: {
              mode: config.report_mode,
              user_input: trimmed,
              session_id: row.id,
              ...(frameworkTemplateId
                ? { report_template_id: frameworkTemplateId }
                : {}),
              ...(forceCacheRefresh ? { force_cache_refresh: true } : {}),
            },
            attachments,
          });
        }
        // One-shot flag: re-arm on each dispatch.
        if (forceCacheRefresh) setForceCacheRefresh(false);
      } catch (err) {
        setStartError(err instanceof Error ? err.message : t("equity_research.research_start_failed"));
      }
    },
    [
      config,
      resetReport,
      startReport,
      disabledConnectorIds,
      disabledSkillIds,
      frameworkTemplateId,
      forceCacheRefresh,
      engineV2Enabled,
      v2Stream,
      t,
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
    fileViewer.close();
  }, [fileViewer]);

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
    fileViewer.close();
  }, [fileViewer]);

  // Publish chat-header state to the global TopBar so the breadcrumb
  // dropdown + New Chat button render. Register on welcome state too
  // (chatTitle null hides the chat crumb, but the New Chat button stays).
  const { register, clear } = useChatHeaderRegistry();
  useEffect(() => {
    register({
      departmentId: "equity_research",
      activeSessionId: sessionId,
      chatTitle: sessionId ? sessionTitle : t("nav.new_chat"),
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
    t,
  ]);

  const handleSave = async (id: string) => {
    await saveReportToRepo(id);
  };

  const handleUnsave = async (id: string) => {
    await unsaveFromRepo(id);
  };

  const handleDelete = async (id: string) => {
    await deleteReport(id);
    // Card flips to tombstone state on next render via expiredAt prop.
    setRestoredExpiredAt(new Date().toISOString());
    setSchema(null);
    setRestoredTombstone((prev) =>
      prev ?? { title: schema?.cover.title ?? "Report", createdAt: new Date().toISOString() },
    );
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
    ? t("equity_research.followup_placeholder")
    : t("equity_research.ticker_placeholder");

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
                  message={reportState.errorMessage ?? t("equity_research.report_generation_failed")}
                  onRetry={() => retryReport()}
                />
              ) : null}

              {schema &&
              !restoredExpiredAt &&
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
                    onSave={handleSave}
                    onUnsave={handleUnsave}
                    onDelete={handleDelete}
                  />
                </div>
              ) : null}

              {restoredExpiredAt && restoredReportId && restoredTombstone ? (
                <div data-testid="er-report-card-tombstone-wrap">
                  <ReportCard
                    reportId={restoredReportId}
                    mode={config.report_mode}
                    ticker={ticker ?? null}
                    companyName={company ?? null}
                    subject={subject || sessionTitle || ""}
                    createdAt={restoredTombstone.createdAt}
                    preview=""
                    onOpen={openReport}
                    onSave={handleSave}
                    expiredAt={restoredExpiredAt}
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
                  {t("common.loading")}
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

      {!sessionId ? (
        <div className="mx-auto w-full max-w-3xl px-4 pb-2">
          <FrameworkTemplatePicker
            selectedId={frameworkTemplateId}
            onChange={setFrameworkTemplateId}
          />
          {capabilityManifest ? (
            <details
              data-testid="er-capability-manifest"
              className="mt-3 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-4 py-2 text-xs"
            >
              <summary className="cursor-pointer select-none text-[--color-text-tertiary] hover:text-[--color-text-primary]">
                Engine v{capabilityManifest.engine_version} — show capabilities
              </summary>
              <div className="mt-3">
                <CapabilitySidebar manifest={capabilityManifest} />
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

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
        forceCacheRefresh={forceCacheRefresh}
        onForceCacheRefreshChange={setForceCacheRefresh}
        engineV2Enabled={engineV2Enabled}
        onEngineV2EnabledChange={setEngineV2Enabled}
        onClose={() => setSettingsOpen(false)}
        onSave={async (p) => {
          await patch(p);
        }}
      />

      {v2Stream.state.status === "paused" && v2Stream.state.pausedOutput &&
       v2Stream.state.runId ? (
        <ClarifierModal
          output={v2Stream.state.pausedOutput}
          round={v2Stream.state.pausedRound ?? 1}
          onSubmit={(answers) => {
            v2Stream.resume({
              runId: v2Stream.state.runId!,
              answers: {
                warning_actions: answers.warningActions,
                clarifications: answers.clarifications,
                question_answers: answers.questionAnswers,
              },
            });
          }}
          onCancel={() => {
            v2Stream.stop();
            v2Stream.reset();
          }}
        />
      ) : null}
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

