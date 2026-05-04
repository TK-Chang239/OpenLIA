import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { type ChatMessage, listMessages } from "../../api/chat";
import { ChatInput } from "./ChatInput";
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
  streamUrl,
  bodyExtras,
  extraInlineMessages,
  extraIsStreaming,
  onExtraStop,
  mode = "personal",
}: Props): JSX.Element {
  const aboutGate = useDisclaimerGate(mode);
  const [aboutOpen, setAboutOpen] = useState(false);

  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sentOnce, setSentOnce] = useState(false);
  const lastSentRef = useRef<string>("");
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
    reset();
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

  const onSend = (text: string) => {
    if (!sessionId) return;
    lastSentRef.current = text;
    setSentOnce(true);
    setHistory((prev) => [
      ...prev,
      {
        id: `optimistic-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        role: "user",
        content: text,
        tool_calls: null,
        model_ref: null,
        token_usage: null,
        created_at: new Date().toISOString(),
      },
    ]);
    send(text);
  };

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
            {history.flatMap((m) => {
              const node =
                m.role === "user" ? (
                  <UserBubble key={m.id} content={m.content} />
                ) : (
                  <HistoricalAssistantMessage key={m.id} message={m} />
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
                  {state.toolCalls.map((c) => (
                    <ToolCallChip
                      key={c.callId}
                      toolName={c.toolName}
                      argsPreview={c.argsPreview}
                      status={c.status}
                      summary={c.summary}
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
      <ChatInput onSend={onSend} onStop={handleStop} isStreaming={isStreaming} placeholder={inputPlaceholder} />
    </div>
  );
}

function HistoricalAssistantMessage({ message }: { message: ChatMessage }): JSX.Element {
  const toolCalls = (message.tool_calls as PersistedToolCall[] | null) ?? null;
  const redirects =
    toolCalls?.filter(
      (c) => c.tool_name === "suggest_redirect" && c.status === "done" && c.structured,
    ) ?? [];
  return (
    <>
      {toolCalls && toolCalls.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {toolCalls.map((c) => (
            <ToolCallChip
              key={c.call_id}
              toolName={c.tool_name}
              argsPreview={c.args_preview}
              status={c.status}
              summary={c.summary}
            />
          ))}
        </div>
      ) : null}
      <AssistantMessage content={message.content} streaming={false} />
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
