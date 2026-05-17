/**
 * useReportStream — POST-based named-event SSE consumer for report generation.
 *
 * Departments that generate reports (Equity Research, Earnings Update,
 * Morning Briefing, Macro Research, Panic Thermometer) all POST a
 * small JSON body to their `/report` endpoint and receive a stream of
 * `report.*` events, terminating in `report.saved` (backend persists
 * then emits the `report_id`) or `report.error`.
 *
 * Wire contract (matches routes that use `event: <type>\ndata: <json>\n\n`):
 *   - report.start    { report_id, department, mode, section_titles[] }
 *   - report.phase    { report_id, phase: 'fetching_data'|'writing'|'finalizing' }
 *   - report.tool_call.start { report_id, call_id, tool_name, args_preview }
 *   - report.tool_call{ report_id, tool_name, summary, call_id }
 *   - report.complete { report_id, schema }   — schema delivered; not yet saved
 *   - report.saved    { report_id }           — persisted, safe to fetch
 *   - report.error    { report_id?, message }
 */
import { useCallback, useEffect, useReducer, useRef } from "react";

export type ReportPhase = "fetching_data" | "writing" | "finalizing";

export type ReportStreamStatus =
  | "idle"
  | "starting"
  | "writing"
  | "complete"
  | "error";

export type SectionStatus = "pending" | "writing" | "done";

export interface SectionView {
  id: string;
  title: string;
  status: SectionStatus;
}

export type ToolCallStatus = "running" | "done";

export interface ReportToolCallView {
  callId: string;
  toolName: string;
  argsPreview: string;
  status: ToolCallStatus;
  summary?: string;
}

export interface ReportStreamState {
  status: ReportStreamStatus;
  phase: ReportPhase | null;
  sectionTitles: string[];
  sections: SectionView[];
  toolCalls: ReportToolCallView[];
  reportId: string | null;
  errorMessage: string | null;
}

const INITIAL: ReportStreamState = {
  status: "idle",
  phase: null,
  sectionTitles: [],
  sections: [],
  toolCalls: [],
  reportId: null,
  errorMessage: null,
};

type Action =
  | { kind: "START" }
  | { kind: "STOP" }
  | { kind: "RESET" }
  | { kind: "EVENT"; event: string; data: Record<string, unknown> };

function reducer(state: ReportStreamState, action: Action): ReportStreamState {
  if (action.kind === "RESET") return INITIAL;
  if (action.kind === "START") return { ...INITIAL, status: "starting" };
  if (action.kind === "STOP")
    return state.status === "complete" || state.status === "error"
      ? state
      : { ...state, status: "error", errorMessage: "Aborted" };
  const { event, data } = action;
  switch (event) {
    case "report.start": {
      const titles = Array.isArray(data.section_titles)
        ? (data.section_titles as string[])
        : [];
      return {
        ...state,
        status: "writing",
        sectionTitles: titles,
        sections: titles.map((t) => ({
          id: "",
          title: t,
          status: "pending" as const,
        })),
      };
    }
    case "report.phase":
      return { ...state, phase: (data.phase as ReportPhase) ?? null };
    case "report.section.start": {
      const id = String(data.section_id ?? "");
      const title = String(data.title ?? "");
      const idx = typeof data.idx === "number" ? data.idx : -1;
      const next = [...state.sections];
      // Prefer matching by idx (start emits ordered events with stable idx).
      if (idx >= 0 && idx < next.length) {
        next[idx] = { id, title, status: "writing" };
      } else if (next.length === 0) {
        next.push({ id, title, status: "writing" });
      } else {
        const i = next.findIndex((s) => s.title === title);
        if (i >= 0) next[i] = { ...next[i], id, status: "writing" };
        else next.push({ id, title, status: "writing" });
      }
      return { ...state, sections: next };
    }
    case "report.section.complete": {
      const id = String(data.section_id ?? "");
      const next = state.sections.map((s) =>
        s.id && s.id === id
          ? { ...s, status: "done" as const }
          : s,
      );
      return { ...state, sections: next };
    }
    case "report.tool_call.start": {
      const callId = String(data.call_id ?? "");
      return {
        ...state,
        toolCalls: [
          ...state.toolCalls,
          {
            callId,
            toolName: String(data.tool_name ?? ""),
            argsPreview: String(data.args_preview ?? ""),
            status: "running" as const,
          },
        ],
      };
    }
    case "report.tool_call": {
      const callId = String(data.call_id ?? "");
      const toolName = String(data.tool_name ?? "");
      const summary = String(data.summary ?? "");
      const idx = callId
        ? state.toolCalls.findIndex((c) => c.callId === callId)
        : -1;
      if (idx >= 0) {
        const next = [...state.toolCalls];
        next[idx] = { ...next[idx], status: "done", summary };
        return { ...state, toolCalls: next };
      }
      return {
        ...state,
        toolCalls: [
          ...state.toolCalls,
          {
            callId,
            toolName,
            argsPreview: "",
            status: "done" as const,
            summary,
          },
        ],
      };
    }
    case "report.complete":
      // Schema has arrived but `report.saved` follows with the persisted id.
      return state;
    case "report.saved":
      return {
        ...state,
        status: "complete",
        reportId: String(data.report_id ?? ""),
      };
    case "report.error":
      return {
        ...state,
        status: "error",
        errorMessage: String(data.message ?? "Report generation failed"),
      };
    default:
      return state;
  }
}

export interface StartOptions {
  url: string;
  body: unknown;
  /** When non-empty, the request is sent as multipart/form-data with the
   *  body's primitive fields as form fields and these files appended as
   *  ``files[]`` entries. JSON path stays in use when omitted/empty. */
  attachments?: File[];
}

/**
 * Attach-only variant: given a persisted report_id, open a GET-based
 * EventSource against `/reports/{id}/stream` and drive the same reducer.
 * Returns the stream state so callers can observe progress on a report
 * that was already started (e.g. after a page reload with ?report_id=).
 */
export function useReportStreamAttach(reportId: string | null): ReportStreamState {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  useEffect(() => {
    if (!reportId) return;
    const es = new EventSource(`/reports/${reportId}/stream`);
    const handle = (event: string) => (e: MessageEvent) => {
      try {
        dispatch({ kind: "EVENT", event, data: JSON.parse(e.data as string) });
      } catch {
        // ignore malformed frames
      }
    };
    for (const evt of [
      "report.start",
      "report.phase",
      "report.section.start",
      "report.section.complete",
      "report.tool_call.start",
      "report.tool_call",
      "report.complete",
      "report.saved",
      "report.error",
    ]) {
      es.addEventListener(evt, handle(evt) as EventListener);
    }
    return () => es.close();
  }, [reportId]);
  return state;
}

export function useReportStream() {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const abortRef = useRef<AbortController | null>(null);
  const lastOptionsRef = useRef<StartOptions | null>(null);

  const start = useCallback(({ url, body, attachments }: StartOptions) => {
    abortRef.current?.abort();
    lastOptionsRef.current = { url, body, attachments };
    dispatch({ kind: "START" });
    const controller = new AbortController();
    abortRef.current = controller;
    void consume({
      url,
      body,
      attachments,
      signal: controller.signal,
      onEvent: (event, data) => dispatch({ kind: "EVENT", event, data }),
      onError: (message) =>
        dispatch({ kind: "EVENT", event: "report.error", data: { message } }),
    });
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ kind: "STOP" });
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    lastOptionsRef.current = null;
    dispatch({ kind: "RESET" });
  }, []);

  const retry = useCallback(() => {
    const opts = lastOptionsRef.current;
    if (!opts) return;
    start(opts);
  }, [start]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  return { state, start, stop, reset, retry };
}

interface ConsumeArgs {
  url: string;
  body: unknown;
  attachments?: File[];
  signal: AbortSignal;
  onEvent: (event: string, data: Record<string, unknown>) => void;
  onError: (message: string) => void;
}

async function consume({
  url,
  body,
  attachments,
  signal,
  onEvent,
  onError,
}: ConsumeArgs) {
  try {
    const useMultipart = (attachments?.length ?? 0) > 0;
    let init: RequestInit;
    if (useMultipart) {
      const fd = new FormData();
      for (const [k, v] of Object.entries(body as Record<string, unknown>)) {
        if (v == null) continue;
        fd.set(k, String(v));
      }
      for (const f of attachments ?? []) fd.append("files", f, f.name);
      init = {
        method: "POST",
        credentials: "include",
        headers: { accept: "text/event-stream" },
        body: fd,
        signal,
      };
    } else {
      init = {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal,
      };
    }
    const res = await fetch(url, init);
    if (!res.ok || !res.body) {
      onError(`report stream HTTP ${res.status}`);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const { event, data } = parseFrame(frame);
        if (!event || !data) continue;
        try {
          onEvent(event, JSON.parse(data));
        } catch (err) {
          console.warn(`malformed report SSE frame for ${event}`, err, data);
        }
      }
    }
  } catch (err) {
    if ((err as { name?: string })?.name === "AbortError") return;
    onError(err instanceof Error ? err.message : "Network error");
  }
}

function parseFrame(frame: string): { event: string; data: string } {
  let event = "";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7).trim();
    else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
  }
  return { event, data: dataLines.join("\n") };
}
