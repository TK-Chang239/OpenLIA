import { useCallback, useEffect, useReducer, useRef } from "react";

export interface ToolCallView {
  callId: string;
  toolName: string;
  argsPreview: string;
  status: "running" | "done" | "failed";
  summary?: string;
}

export type ChatStreamEvent =
  | { type: "chat.start"; data: Record<string, unknown> }
  | {
      type: "chat.tool_call.start";
      data: { call_id: string; tool_name: string; args_preview: string };
    }
  | { type: "chat.tool_call.result"; data: { call_id: string; ok: boolean; summary: string } }
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
  message: string;
  toolCalls: ToolCallView[];
  reportThumbnails: Array<{ report_id: string; filename: string }>;
  errorMessage: string | null;
}

const INITIAL: StreamState = {
  status: "idle",
  message: "",
  toolCalls: [],
  reportThumbnails: [],
  errorMessage: null,
};

type Action =
  | { kind: "SEND" }
  | { kind: "EVENT"; event: ChatStreamEvent }
  | { kind: "STOP" }
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
          ? { ...c, status: (ev.data.ok ? "done" : "failed") as "done" | "failed", summary: ev.data.summary }
          : c,
      );
      return { ...state, toolCalls: next };
    }
    case "chat.token":
      return { ...state, status: "streaming", message: state.message + ev.data.text };
    case "chat.report_thumbnail":
      return { ...state, reportThumbnails: [...state.reportThumbnails, ev.data] };
    case "chat.done":
      return { ...state, status: "done" };
    case "chat.error":
      return { ...state, status: "error", errorMessage: ev.data.message };
    default:
      return state;
  }
}

interface Options {
  sessionId: string;
}

export function useChatStream({ sessionId }: Options) {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const sourceRef = useRef<EventSource | null>(null);

  const send = useCallback(
    (userMessage: string) => {
      sourceRef.current?.close();
      dispatch({ kind: "SEND" });
      const qs = new URLSearchParams({ q: userMessage });
      const es = new EventSource(
        `/api/chat/sessions/${sessionId}/stream?${qs.toString()}`,
        { withCredentials: true },
      );
      const handler =
        (type: ChatStreamEvent["type"]) =>
        (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data);
            dispatch({ kind: "EVENT", event: { type, data } as ChatStreamEvent });
            if (type === "chat.done" || type === "chat.error") es.close();
          } catch {
            // malformed event — ignore
          }
        };
      (
        [
          "chat.start",
          "chat.tool_call.start",
          "chat.tool_call.result",
          "chat.token",
          "chat.report_thumbnail",
          "chat.done",
          "chat.error",
        ] as const
      ).forEach((t) => es.addEventListener(t, handler(t)));
      es.addEventListener("error", () => {
        dispatch({
          kind: "EVENT",
          event: { type: "chat.error", data: { message: "Connection lost. Please try again." } },
        });
        es.close();
      });
      sourceRef.current = es;
    },
    [sessionId],
  );

  const stop = useCallback(() => {
    sourceRef.current?.close();
    dispatch({ kind: "STOP" });
  }, []);

  const reset = useCallback(() => {
    sourceRef.current?.close();
    dispatch({ kind: "RESET" });
  }, []);

  useEffect(() => () => { sourceRef.current?.close(); }, []);

  return { state, send, stop, reset };
}
