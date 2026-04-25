import { useCallback, useEffect, useReducer, useRef } from "react";
import { createParser, type EventSourceMessage } from "eventsource-parser";

export interface ToolCallView {
  callId: string;
  toolName: string;
  argsPreview: string;
  status: "running" | "done" | "failed";
  summary?: string;
  structured?: Record<string, unknown> | null;
}

export type AssistantChunk =
  | { type: "text"; text: string }
  | { type: "thumbnail"; report_id: string; filename: string };

export type ChatStreamEvent =
  | { type: "chat.start"; data: Record<string, unknown> }
  | {
      type: "chat.tool_call.start";
      data: { call_id: string; tool_name: string; args_preview: string };
    }
  | {
      type: "chat.tool_call.result";
      data: {
        call_id: string;
        ok: boolean;
        summary: string;
        structured?: Record<string, unknown> | null;
      };
    }
  | { type: "chat.token"; data: { text: string } }
  | { type: "chat.report_thumbnail"; data: { report_id: string; filename: string } }
  | { type: "chat.done"; data: Record<string, unknown> }
  | { type: "chat.error"; data: { message: string } };

export type StreamStatus =
  | "idle"
  | "opening"
  | "thinking"
  | "streaming"
  | "done"
  | "error"
  | "stopped";

export interface StreamState {
  status: StreamStatus;
  /** Concatenated text-chunk content. Convenience accessor for callers
   *  that don't need inline ordering. Equivalent to chunks-of-text joined. */
  message: string;
  /** Inline-ordered chunks (text + report thumbnails) used by the
   *  AssistantMessage renderer. */
  chunks: AssistantChunk[];
  toolCalls: ToolCallView[];
  /** Flat thumbnail list — kept for back-compat with existing tests/UI. */
  reportThumbnails: Array<{ report_id: string; filename: string }>;
  errorMessage: string | null;
}

const INITIAL: StreamState = {
  status: "idle",
  message: "",
  chunks: [],
  toolCalls: [],
  reportThumbnails: [],
  errorMessage: null,
};

type Action =
  | { kind: "SEND" }
  | { kind: "EVENT"; event: ChatStreamEvent }
  | { kind: "STOP" }
  | { kind: "TRANSPORT_ERROR" }
  | { kind: "RESET" };

function isTerminal(s: StreamStatus): boolean {
  return s === "done" || s === "error" || s === "stopped";
}

function reducer(state: StreamState, action: Action): StreamState {
  if (action.kind === "RESET") return INITIAL;
  if (action.kind === "SEND") return { ...INITIAL, status: "opening" };
  if (action.kind === "STOP") {
    if (isTerminal(state.status)) return state;
    return { ...state, status: "stopped" };
  }
  if (action.kind === "TRANSPORT_ERROR") {
    if (isTerminal(state.status)) return state;
    // If any tokens arrived, treat as a soft stop; otherwise surface as error.
    if (state.message.length > 0) return { ...state, status: "stopped" };
    return {
      ...state,
      status: "error",
      errorMessage: "Connection lost. Please try again.",
    };
  }
  if (isTerminal(state.status)) return state;
  const ev = action.event;
  switch (ev.type) {
    case "chat.start":
      return { ...state, status: "thinking" };
    case "chat.tool_call.start":
      return {
        ...state,
        toolCalls: [
          ...state.toolCalls,
          {
            callId: ev.data.call_id,
            toolName: ev.data.tool_name,
            argsPreview: ev.data.args_preview,
            status: "running",
          },
        ],
      };
    case "chat.tool_call.result": {
      const next = state.toolCalls.map((c) =>
        c.callId === ev.data.call_id
          ? {
              ...c,
              status: (ev.data.ok ? "done" : "failed") as "done" | "failed",
              summary: ev.data.summary,
              structured: ev.data.structured ?? null,
            }
          : c,
      );
      return { ...state, toolCalls: next };
    }
    case "chat.token": {
      const text = ev.data.text;
      // Merge with the trailing text chunk when present so consecutive
      // tokens collapse into one chunk for the renderer.
      const chunks = [...state.chunks];
      const last = chunks[chunks.length - 1];
      if (last && last.type === "text") {
        chunks[chunks.length - 1] = { type: "text", text: last.text + text };
      } else {
        chunks.push({ type: "text", text });
      }
      return {
        ...state,
        status: "streaming",
        message: state.message + text,
        chunks,
      };
    }
    case "chat.report_thumbnail":
      return {
        ...state,
        chunks: [
          ...state.chunks,
          {
            type: "thumbnail",
            report_id: ev.data.report_id,
            filename: ev.data.filename,
          },
        ],
        reportThumbnails: [...state.reportThumbnails, ev.data],
      };
    case "chat.done":
      return { ...state, status: "done" };
    case "chat.error":
      return { ...state, status: "error", errorMessage: ev.data.message };
    default:
      return state;
  }
}

const KNOWN_EVENT_TYPES: ReadonlyArray<ChatStreamEvent["type"]> = [
  "chat.start",
  "chat.tool_call.start",
  "chat.tool_call.result",
  "chat.token",
  "chat.report_thumbnail",
  "chat.done",
  "chat.error",
];

interface Options {
  sessionId: string;
  /** Pluggable transport for tests; defaults to ``window.fetch``. */
  fetchImpl?: typeof fetch;
}

interface StopReason {
  /** True when the user invoked ``stop()`` — abort, do not auto-reconnect. */
  intentional: boolean;
}

interface ActiveStream {
  controller: AbortController;
  /** Mark the in-flight stream as user-stopped before aborting. */
  reason: StopReason;
}

export function useChatStream({ sessionId, fetchImpl }: Options) {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const activeRef = useRef<ActiveStream | null>(null);
  const reconnectAttemptedRef = useRef<boolean>(false);

  const fetcher = fetchImpl ?? (typeof fetch !== "undefined" ? fetch : undefined);

  const closeActive = useCallback((intentional: boolean) => {
    const active = activeRef.current;
    if (!active) return;
    active.reason.intentional = intentional;
    activeRef.current = null;
    try {
      active.controller.abort();
    } catch {
      // ignore
    }
  }, []);

  const runStream = useCallback(
    async (userMessage: string, isReconnect: boolean): Promise<void> => {
      if (!fetcher) {
        dispatch({
          kind: "EVENT",
          event: {
            type: "chat.error",
            data: { message: "fetch is not available in this environment" },
          },
        });
        return;
      }
      const controller = new AbortController();
      const reason: StopReason = { intentional: false };
      activeRef.current = { controller, reason };

      let response: Response;
      try {
        response = await fetcher(`/api/chat/sessions/${sessionId}/stream`, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({ q: userMessage }),
          signal: controller.signal,
        });
      } catch (err) {
        if (reason.intentional) return;
        if (controller.signal.aborted) return;
        if (!isReconnect && !reconnectAttemptedRef.current) {
          reconnectAttemptedRef.current = true;
          await runStream(userMessage, true);
          return;
        }
        dispatch({ kind: "TRANSPORT_ERROR" });
        return;
      }

      if (!response.ok || !response.body) {
        dispatch({
          kind: "EVENT",
          event: {
            type: "chat.error",
            data: { message: `Request failed (${response.status})` },
          },
        });
        return;
      }

      let receivedTerminal = false;
      const parser = createParser({
        onEvent: (msg: EventSourceMessage) => {
          const type = (msg.event ?? "").trim();
          if (!type) return;
          if (!KNOWN_EVENT_TYPES.includes(type as ChatStreamEvent["type"])) return;
          try {
            const data = JSON.parse(msg.data);
            if (type === "chat.done" || type === "chat.error") {
              receivedTerminal = true;
            }
            dispatch({
              kind: "EVENT",
              event: { type, data } as ChatStreamEvent,
            });
          } catch (err) {
            // Malformed frames are dropped silently.
            console.warn(`malformed SSE frame for ${type}`, err);
          }
        },
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          parser.feed(decoder.decode(value, { stream: true }));
        }
      } catch {
        // Transport-level errors fall through to the post-loop branch
        // where we differentiate stopped vs error via state.message.
      } finally {
        try {
          reader.releaseLock();
        } catch {
          // ignore
        }
      }

      if (reason.intentional) return;
      if (controller.signal.aborted) return;
      if (receivedTerminal) return;
      // Stream closed without a terminal event. Try one auto-reconnect for
      // transient drops, then surface the error/stopped taxonomy.
      if (!isReconnect && !reconnectAttemptedRef.current) {
        reconnectAttemptedRef.current = true;
        await runStream(userMessage, true);
        return;
      }
      dispatch({ kind: "TRANSPORT_ERROR" });
    },
    [fetcher, sessionId],
  );

  const send = useCallback(
    (userMessage: string) => {
      closeActive(true);
      reconnectAttemptedRef.current = false;
      dispatch({ kind: "SEND" });
      void runStream(userMessage, false);
    },
    [closeActive, runStream],
  );

  const stop = useCallback(() => {
    closeActive(true);
    dispatch({ kind: "STOP" });
  }, [closeActive]);

  const reset = useCallback(() => {
    closeActive(true);
    dispatch({ kind: "RESET" });
  }, [closeActive]);

  useEffect(() => {
    closeActive(true);
    dispatch({ kind: "RESET" });
    return () => {
      closeActive(true);
    };
  }, [sessionId, closeActive]);

  return { state, send, stop, reset };
}
