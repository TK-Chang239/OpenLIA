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
 *   - report.tool_call{ report_id, tool_name, summary }
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

export interface ReportStreamState {
  status: ReportStreamStatus;
  phase: ReportPhase | null;
  sectionTitles: string[];
  toolCalls: { tool: string; summary: string }[];
  reportId: string | null;
  errorMessage: string | null;
}

const INITIAL: ReportStreamState = {
  status: "idle",
  phase: null,
  sectionTitles: [],
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
    case "report.start":
      return {
        ...state,
        status: "writing",
        sectionTitles: Array.isArray(data.section_titles)
          ? (data.section_titles as string[])
          : [],
      };
    case "report.phase":
      return { ...state, phase: (data.phase as ReportPhase) ?? null };
    case "report.tool_call":
      return {
        ...state,
        toolCalls: [
          ...state.toolCalls,
          {
            tool: String(data.tool_name ?? ""),
            summary: String(data.summary ?? ""),
          },
        ],
      };
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
}

export function useReportStream() {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(({ url, body }: StartOptions) => {
    abortRef.current?.abort();
    dispatch({ kind: "START" });
    const controller = new AbortController();
    abortRef.current = controller;
    void consume({
      url,
      body,
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
    dispatch({ kind: "RESET" });
  }, []);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  return { state, start, stop, reset };
}

interface ConsumeArgs {
  url: string;
  body: unknown;
  signal: AbortSignal;
  onEvent: (event: string, data: Record<string, unknown>) => void;
  onError: (message: string) => void;
}

async function consume({ url, body, signal, onEvent, onError }: ConsumeArgs) {
  try {
    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
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
