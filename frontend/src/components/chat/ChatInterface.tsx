import { useEffect, useMemo, useRef, useState } from "react";
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
import { ReportThumbnail } from "./ReportThumbnail";
import { RedirectCard, type RedirectDepartment } from "./RedirectCard";

interface Chip {
  label: string;
  value: string;
}

interface Props {
  sessionId: string;
  greeting: string;
  subtext: string;
  chips: Chip[];
  inputPlaceholder: string;
  /** Optional one-shot message dispatched automatically on mount. */
  initialMessage?: string | null;
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
}: Props): JSX.Element {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sentOnce, setSentOnce] = useState(false);
  const lastSentRef = useRef<string>("");
  const { state, send, stop, reset } = useChatStream({ sessionId });

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

  const isStreaming =
    state.status === "opening" || state.status === "thinking" || state.status === "streaming";

  const showWelcome = loaded && !sentOnce && !loadError;

  const autoscrollKey = useMemo(
    () => `${history.length}:${state.message.length}:${state.toolCalls.length}`,
    [history.length, state.message.length, state.toolCalls.length],
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
            {history.map((m) =>
              m.role === "user" ? (
                <UserBubble key={m.id} content={m.content} />
              ) : (
                <HistoricalAssistantMessage key={m.id} message={m} />
              ),
            )}
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
            state.message ? (
              <AssistantMessage
                content={state.message}
                streaming={state.status === "streaming"}
                stopped={state.status === "stopped"}
              />
            ) : null}
            {state.reportThumbnails.map((t) => (
              <ReportThumbnail key={t.report_id} reportId={t.report_id} filename={t.filename} />
            ))}
            {state.status === "error" && state.errorMessage ? (
              <ErrorMessage
                message={state.errorMessage}
                onRetry={() => send(lastSentRef.current)}
              />
            ) : null}
          </MessageList>
        ) : null}
      </div>
      <ChatInput onSend={onSend} onStop={stop} isStreaming={isStreaming} placeholder={inputPlaceholder} />
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
