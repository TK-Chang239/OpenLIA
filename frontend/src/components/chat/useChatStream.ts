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
  | { type: "chat.error"; data: { message: string } }
  | {
      type: "chat.guardrail";
      data: {
        category: string;
        action: "replaced" | "warned" | "logged";
        replacement?: string | null;
        chip_text?: string | null;
      };
    }
  | {
      type: "chat.skill_loaded";
      data: { skill_id: string; display_name: string };
    }
  | {
      type: "chat.memory_block";
      data: { message_id: string; block: string | null };
    };

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
  flagChips: Array<{ category: string; text: string }>;
  skillLoads: Array<{ skillId: string; displayName: string }>;
  /** Cross-session memory block injected into the system prompt for this
   *  turn (rendered ``## Memory`` markdown). Null when the backend chose
   *  not to inject anything, undefined until the first event fires. */
  memoryBlock: string | null | undefined;
  errorMessage: string | null;
  /** Wall-clock timestamp (ms since epoch) when the SEND action was
   *  dispatched. null until the next send. Internal — used to compute
   *  latencyMs on terminal transitions. */
  startedAt: number | null;
  /** Wall-clock latency from SEND → terminal state, in milliseconds.
   *  Populated when status transitions to done/stopped. */
  latencyMs: number | null;
  /** Total token count from chat.done event when the backend reports it,
   *  otherwise null. */
  tokens: number | null;
}

const INITIAL: StreamState = {
  status: "idle",
  message: "",
  chunks: [],
  toolCalls: [],
  reportThumbnails: [],
  flagChips: [],
  skillLoads: [],
  memoryBlock: undefined,
  errorMessage: null,
  startedAt: null,
  latencyMs: null,
  tokens: null,
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

function nowMs(): number {
  return typeof performance !== "undefined" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();
}

function reducer(state: StreamState, action: Action): StreamState {
  if (action.kind === "RESET") return INITIAL;
  if (action.kind === "SEND")
    return { ...INITIAL, status: "opening", startedAt: nowMs() };
  if (action.kind === "STOP") {
    if (isTerminal(state.status)) return state;
    const latencyMs =
      state.startedAt !== null ? Math.round(nowMs() - state.startedAt) : null;
    return { ...state, status: "stopped", latencyMs };
  }
  if (action.kind === "TRANSPORT_ERROR") {
    if (isTerminal(state.status)) return state;
    const latencyMs =
      state.startedAt !== null ? Math.round(nowMs() - state.startedAt) : null;
    // If any tokens arrived, treat as a soft stop; otherwise surface as error.
    if (state.message.length > 0)
      return { ...state, status: "stopped", latencyMs };
    return {
      ...state,
      status: "error",
      errorMessage: "Connection lost. Please try again.",
      latencyMs,
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
    case "chat.done": {
      const latencyMs =
        state.startedAt !== null ? Math.round(nowMs() - state.startedAt) : null;
      // chat.done sometimes carries token usage as { tokens: number } or
      // { token_usage: { total_tokens: number } } — tolerate both shapes.
      const data = ev.data ?? {};
      let tokens: number | null = null;
      if (typeof data.tokens === "number" && Number.isFinite(data.tokens)) {
        tokens = data.tokens;
      } else if (
        data.token_usage &&
        typeof (data.token_usage as Record<string, unknown>).total_tokens === "number"
      ) {
        tokens = (data.token_usage as Record<string, unknown>).total_tokens as number;
      }
      return { ...state, status: "done", latencyMs, tokens };
    }
    case "chat.error": {
      const latencyMs =
        state.startedAt !== null ? Math.round(nowMs() - state.startedAt) : null;
      return { ...state, status: "error", errorMessage: ev.data.message, latencyMs };
    }
    case "chat.guardrail": {
      const action = ev.data.action;
      if (action === "replaced") {
        const replacement = ev.data.replacement ?? "";
        return {
          ...state,
          message: replacement,
          chunks: [{ type: "text", text: replacement }],
        };
      }
      if (action === "warned") {
        const text = ev.data.chip_text ?? "";
        return {
          ...state,
          flagChips: [...state.flagChips, { category: ev.data.category, text }],
        };
      }
      return state;
    }
    case "chat.skill_loaded":
      return {
        ...state,
        skillLoads: [
          ...state.skillLoads,
          { skillId: ev.data.skill_id, displayName: ev.data.display_name },
        ],
      };
    case "chat.memory_block":
      return { ...state, memoryBlock: ev.data.block };
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
  "chat.guardrail",
  "chat.skill_loaded",
  "chat.memory_block",
];

interface Options {
  sessionId: string;
  /** Pluggable transport for tests; defaults to ``window.fetch``. */
  fetchImpl?: typeof fetch;
  /** Override the default `/api/chat/sessions/{id}/stream` endpoint. */
  streamUrl?: string;
  /** Extra fields merged into the JSON request body (e.g. `{ session_id }`). */
  bodyExtras?: Record<string, unknown>;
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

export function useChatStream({ sessionId, fetchImpl, streamUrl, bodyExtras }: Options) {
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
    async (
      userMessage: string,
      isReconnect: boolean,
      attachments?: File[],
    ): Promise<void> => {
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
      const url = streamUrl ?? `/api/chat/sessions/${sessionId}/stream`;
      const useMultipart = (attachments?.length ?? 0) > 0;
      let init: RequestInit;
      if (useMultipart) {
        const fd = new FormData();
        fd.set("message", userMessage);
        for (const [k, v] of Object.entries(bodyExtras ?? {})) {
          if (v == null) continue;
          fd.set(k, String(v));
        }
        for (const f of attachments ?? []) {
          fd.append("files", f, f.name);
        }
        init = {
          method: "POST",
          credentials: "same-origin",
          headers: { Accept: "text/event-stream" },
          body: fd,
          signal: controller.signal,
        };
      } else {
        const body = streamUrl
          ? { message: userMessage, ...(bodyExtras ?? {}) }
          : { q: userMessage, ...(bodyExtras ?? {}) };
        init = {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify(body),
          signal: controller.signal,
        };
      }
      try {
        response = await fetcher(url, init);
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
    [fetcher, sessionId, streamUrl, bodyExtras],
  );

  const send = useCallback(
    (userMessage: string, attachments?: File[]) => {
      closeActive(true);
      reconnectAttemptedRef.current = false;
      dispatch({ kind: "SEND" });
      void runStream(userMessage, false, attachments);
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
