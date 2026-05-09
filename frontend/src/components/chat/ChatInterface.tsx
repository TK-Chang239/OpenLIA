import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import type { UserBubbleAttachment } from "./UserBubble";
import { AnimatePresence } from "framer-motion";
import { type ChatMessage, getSession, listMessages } from "../../api/chat";
import { ChatInput } from "./ChatInput";
import { ModelPicker } from "./ModelPicker";
import { ToolPicker } from "./ToolPicker";
import { MessageList } from "./MessageList";
import { UserBubble } from "./UserBubble";
import { AssistantMessage } from "./AssistantMessage";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { ToolCallChip } from "./ToolCallChip";
import { ErrorMessage } from "./ErrorMessage";
import { WelcomeOverlay } from "./WelcomeOverlay";
import { useChatStream } from "./useChatStream";
import { RedirectCard, type RedirectDepartment } from "./RedirectCard";
import { useDisclaimerGate } from "../../hooks/useDisclaimerGate";
import { AboutLiaModal } from "../safety/AboutLiaModal";

interface Chip {
  label: string;
  value: string;
}

export interface InlineExtraMessage {
  /** Insert AFTER this user message id, or "end" to render after the chat thread. */
  after: string | "end";
  node: ReactNode;
  key: string;
}

interface Props {
  sessionId: string;
  greeting: string;
  subtext: string;
  chips: Chip[];
  inputPlaceholder: string;
  /** Optional one-shot message dispatched automatically on mount. */
  initialMessage?: string | null;
  /** Seeds the composer's textarea on mount without auto-sending. Used by
   *  the Home page's `?prompt=` query-param prefill flow. */
  initialDraft?: string | null;
  /** NEW-14-01: override the default `/api/chat/sessions/{id}/stream` endpoint. */
  streamUrl?: string;
  /** NEW-14-01: extra fields merged into the JSON request body. */
  bodyExtras?: Record<string, unknown>;
  /** NEW-14-02: inline assistant-side nodes injected into the message list. */
  extraInlineMessages?: InlineExtraMessage[];
  /** Treat as actively streaming even when the chat stream is idle (e.g.,
   *  while a sibling report stream is generating). Causes the input to render
   *  the Stop button. */
  extraIsStreaming?: boolean;
  /** Invoked when the user clicks Stop and `extraIsStreaming` is true. */
  onExtraStop?: () => void;
  /** Deployment mode — determines how the About Lia disclaimer is fetched.
   *  Defaults to "personal" when not provided. */
  mode?: "personal" | "company";
  /** When set, the chat input toolbar shows the global LLM model picker.
   *  Selection persists at the user level (``user_prefs.preferred_model_id``)
   *  so it follows the user across all chats and departments. */
  departmentId?: string;
}

interface PersistedToolCall {
  call_id: string;
  tool_name: string;
  args_preview: string;
  status: "running" | "done" | "failed";
  summary?: string;
  structured?: Record<string, unknown> | null;
}

export function ChatInterface({
  sessionId,
  greeting,
  subtext,
  chips,
  inputPlaceholder,
  initialMessage,
  initialDraft,
  streamUrl,
  bodyExtras,
  extraInlineMessages,
  extraIsStreaming,
  onExtraStop,
  mode = "personal",
  departmentId,
}: Props): JSX.Element {
  const aboutGate = useDisclaimerGate(mode);
  const [aboutOpen, setAboutOpen] = useState(false);

  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sentOnce, setSentOnce] = useState(false);
  const [disabledConnectorIds, setDisabledConnectorIds] = useState<string[]>([]);
  const [disabledSkillIds, setDisabledSkillIds] = useState<string[]>([]);
  const lastSentRef = useRef<string>("");
  const persistedStreamRef = useRef<string | null>(null);
  const pendingAttachmentsRef = useRef<Map<string, UserBubbleAttachment[]>>(
    new Map(),
  );
  const { state, send, stop, reset } = useChatStream({
    sessionId,
    streamUrl,
    bodyExtras,
  });

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setLoadError(null);
    setHistory([]);
    setSentOnce(false);
    persistedStreamRef.current = null;
    reset();
    // Fire the session GET in parallel to refresh the disabled-tool lists
    // (the chat-input ToolPicker reads them as initial state). Failures
    // here are non-blocking — we degrade to "all on" defaults.
    getSession(sessionId)
      .then((s) => {
        if (cancelled) return;
        setDisabledConnectorIds(s.disabled_connector_ids ?? []);
        setDisabledSkillIds(s.disabled_skill_ids ?? []);
      })
      .catch(() => {
        if (cancelled) return;
        setDisabledConnectorIds([]);
        setDisabledSkillIds([]);
      });
    listMessages(sessionId)
      .then((r) => {
        if (cancelled) return;
        if (!r) {
          setLoaded(true);
          return;
        }
        setHistory(r.items);
        if (r.items.length > 0) setSentOnce(true);
        setLoaded(true);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : "Failed to load messages");
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
    // `reset` is a stable useCallback([]) from useChatStream.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const onSend = (text: string, attachments?: File[]) => {
    if (!sessionId) return;
    lastSentRef.current = text;
    persistedStreamRef.current = null;
    setSentOnce(true);
    const optimisticId = `optimistic-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setHistory((prev) => [
      ...prev,
      {
        id: optimisticId,
        role: "user",
        content: text,
        tool_calls: null,
        model_ref: null,
        token_usage: null,
        created_at: new Date().toISOString(),
      },
    ]);
    if (attachments && attachments.length > 0) {
      // Cache pending attachments by optimistic message id so the UserBubble
      // renders chips above the text. The actual upload to a session-scoped
      // attachments endpoint is not yet implemented backend-side; once it
      // lands, we POST here, swap pending chips for resolved AttachmentChips,
      // and pass attachment_ids in the chat stream body.
      // TODO: backend upload pending — POST /api/chat/sessions/:id/attachments
      pendingAttachmentsRef.current.set(
        optimisticId,
        attachments.map((f) => ({ filename: f.name, sizeBytes: f.size })),
      );
    }
    send(text);
  };

  // When a stream completes, snapshot the assistant reply into the
  // persistent history so it stays visible after the next user message
  // (which resets the live stream state). The DB persists it server-side
  // independently — this just keeps the local UI in sync without a refetch.
  useEffect(() => {
    if (state.status !== "done" && state.status !== "stopped") return;
    if (state.chunks.length === 0 && !state.message) return;
    const key = `${state.status}|${state.message.length}|${state.toolCalls.length}`;
    if (persistedStreamRef.current === key) return;
    persistedStreamRef.current = key;

    const tool_calls =
      state.toolCalls.length > 0
        ? state.toolCalls.map((c) => ({
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
        content: state.message,
        tool_calls,
        model_ref: null,
        token_usage: null,
        created_at: now,
        stopped_at: state.status === "stopped" ? now : null,
      },
    ]);
    reset();
  }, [state.status, state.message, state.chunks.length, state.toolCalls, reset]);

  const chatStreaming =
    state.status === "opening" || state.status === "thinking" || state.status === "streaming";
  const isStreaming = chatStreaming || Boolean(extraIsStreaming);
  const handleStop = () => {
    if (chatStreaming) stop();
    if (extraIsStreaming) onExtraStop?.();
  };

  const hasInline = (extraInlineMessages?.length ?? 0) > 0;
  const showWelcome = loaded && !sentOnce && !loadError && !hasInline;

  const autoscrollKey = useMemo(
    () =>
      `${history.length}:${state.message.length}:${state.toolCalls.length}:${state.chunks.length}`,
    [
      history.length,
      state.message.length,
      state.toolCalls.length,
      state.chunks.length,
    ],
  );

  const initialSentRef = useRef<string | null>(null);
  useEffect(() => {
    if (!loaded || loadError) return;
    if (!initialMessage) return;
    if (initialSentRef.current === initialMessage) return;
    if (history.length > 0) {
      initialSentRef.current = initialMessage;
      return;
    }
    initialSentRef.current = initialMessage;
    onSend(initialMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, loadError, initialMessage, history.length]);

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center text-[--color-text-tertiary]">
        No chat session selected.
      </div>
    );
  }

  return (
    <div className="relative flex h-full flex-col">
      <div className="flex justify-end px-4 pt-2">
        <button
          onClick={() => setAboutOpen(true)}
          className="text-xs text-slate-500 underline"
        >
          (?) About Lia
        </button>
      </div>
      {aboutOpen && aboutGate.disclaimer && (
        <AboutLiaModal
          text={aboutGate.disclaimer.text}
          onClose={() => setAboutOpen(false)}
        />
      )}
      <div className="relative flex-1">
        <AnimatePresence>
          {showWelcome ? (
            <WelcomeOverlay
              greeting={greeting}
              subtext={subtext}
              chips={chips}
              onChipClick={onSend}
            />
          ) : null}
        </AnimatePresence>
        {loadError ? (
          <div className="flex h-full items-center justify-center p-8">
            <ErrorMessage message={loadError} />
          </div>
        ) : null}
        {!showWelcome && !loadError ? (
          <MessageList autoscrollKey={autoscrollKey}>
            {history.flatMap((m, idx) => {
              const prev = history[idx - 1];
              const latencyMs =
                m.role === "assistant" && prev?.role === "user"
                  ? Math.max(
                      0,
                      new Date(m.created_at).getTime() -
                        new Date(prev.created_at).getTime(),
                    )
                  : null;
              const node =
                m.role === "user" ? (
                  <UserBubble
                    key={m.id}
                    content={m.content}
                    attachments={pendingAttachmentsRef.current.get(m.id)}
                  />
                ) : (
                  <HistoricalAssistantMessage
                    key={m.id}
                    message={m}
                    departmentId={departmentId}
                    latencyMs={latencyMs}
                  />
                );
              const inline = (extraInlineMessages ?? [])
                .filter((x) => x.after === m.id)
                .map((x) => <div key={x.key}>{x.node}</div>);
              return [node, ...inline];
            })}
            {state.status === "thinking" ? <ThinkingIndicator /> : null}
            {state.toolCalls.length > 0 ? (
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap gap-2">
                  {state.toolCalls.map((c, i) => (
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
                {state.toolCalls
                  .filter(
                    (c) =>
                      c.toolName === "suggest_redirect" &&
                      c.status === "done" &&
                      c.structured,
                  )
                  .map((c) => {
                    const s = c.structured as Record<string, unknown>;
                    return (
                      <RedirectCard
                        key={`${c.callId}-redirect`}
                        department={s.department as RedirectDepartment}
                        reason={String(s.reason ?? "")}
                        prefill={
                          typeof s.prefill === "string" ? s.prefill : undefined
                        }
                      />
                    );
                  })}
              </div>
            ) : null}
            {(state.status === "streaming" ||
              state.status === "done" ||
              state.status === "stopped") &&
            (state.chunks.length > 0 || state.message) ? (
              <AssistantMessage
                chunks={state.chunks}
                streaming={state.status === "streaming"}
                stopped={state.status === "stopped"}
                flagChips={state.flagChips}
                skillLoads={state.skillLoads}
                departmentId={departmentId}
                tokens={state.tokens}
                latencyMs={state.latencyMs}
              />
            ) : null}
            {state.status === "error" && state.errorMessage ? (
              <ErrorMessage
                message={state.errorMessage}
                onRetry={() => send(lastSentRef.current)}
              />
            ) : null}
            {(extraInlineMessages ?? [])
              .filter((x) => x.after === "end")
              .map((x) => (
                <div key={x.key}>{x.node}</div>
              ))}
          </MessageList>
        ) : null}
      </div>
      <ChatInput
        onSend={onSend}
        onStop={handleStop}
        isStreaming={isStreaming}
        placeholder={inputPlaceholder}
        initialValue={initialDraft ?? undefined}
        leftSlot={
          departmentId ? (
            <div className="flex items-center gap-2">
              <ModelPicker />
              <ToolPicker
                sessionId={sessionId}
                initialDisabledConnectorIds={disabledConnectorIds}
                initialDisabledSkillIds={disabledSkillIds}
              />
            </div>
          ) : null
        }
      />
    </div>
  );
}

function HistoricalAssistantMessage({
  message,
  departmentId,
  latencyMs,
}: {
  message: ChatMessage;
  departmentId?: string;
  latencyMs?: number | null;
}): JSX.Element {
  const toolCalls = (message.tool_calls as PersistedToolCall[] | null) ?? null;
  const redirects =
    toolCalls?.filter(
      (c) => c.tool_name === "suggest_redirect" && c.status === "done" && c.structured,
    ) ?? [];
  const tokens =
    message.token_usage &&
    typeof (message.token_usage as Record<string, unknown>).total_tokens === "number"
      ? ((message.token_usage as Record<string, unknown>).total_tokens as number)
      : null;
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
        departmentId={departmentId}
        tokens={tokens}
        latencyMs={latencyMs ?? null}
      />
      {redirects.map((c) => {
        const s = c.structured as Record<string, unknown>;
        return (
          <RedirectCard
            key={`${c.call_id}-redirect`}
            department={s.department as RedirectDepartment}
            reason={String(s.reason ?? "")}
            prefill={typeof s.prefill === "string" ? s.prefill : undefined}
          />
        );
      })}
    </>
  );
}
