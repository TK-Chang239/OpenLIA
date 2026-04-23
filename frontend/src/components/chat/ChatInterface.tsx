import { useEffect, useState } from "react";
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
}

export function ChatInterface({
  sessionId,
  greeting,
  subtext,
  chips,
  inputPlaceholder,
}: Props): JSX.Element {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [sentOnce, setSentOnce] = useState(false);
  const { state, send, stop } = useChatStream({ sessionId });

  useEffect(() => {
    listMessages(sessionId).then((r) => {
      setHistory(r.items);
      if (r.items.length > 0) setSentOnce(true);
      setLoaded(true);
    });
  }, [sessionId]);

  const onSend = (text: string) => {
    setSentOnce(true);
    setHistory((prev) => [
      ...prev,
      {
        id: String(-Date.now()),
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

  const showWelcome = loaded && !sentOnce;

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
        {!showWelcome ? (
          <MessageList autoscrollKey={state.message + history.length}>
            {history.map((m) =>
              m.role === "user" ? (
                <UserBubble key={m.id} content={m.content} />
              ) : (
                <AssistantMessage key={m.id} content={m.content} streaming={false} />
              ),
            )}
            {state.status === "thinking" ? <ThinkingIndicator /> : null}
            {state.toolCalls.length > 0 ? (
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
                onRetry={() => send(history[history.length - 1]?.content ?? "")}
              />
            ) : null}
          </MessageList>
        ) : null}
      </div>
      <ChatInput onSend={onSend} onStop={stop} isStreaming={isStreaming} placeholder={inputPlaceholder} />
    </div>
  );
}
