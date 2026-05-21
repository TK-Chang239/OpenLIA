/**
 * useV2ReportStream — POST-based named-event SSE consumer for the v2.2
 * equity-research pipeline.
 *
 * Speaks the event vocabulary emitted by the backend's RunnerV2:
 *   - stage.started     { stage }
 *   - stage.completed   { stage }
 *   - clarifier.pause   { run_id, round, output: ClarifierOutput }
 *   - completed         { run_id, html }
 *   - failed            { run_id, stage, reason }
 *
 * Designed to live alongside the v1 useReportStream rather than replacing
 * it — the equity-research page picks one or the other based on a feature
 * flag.
 */
import { useCallback, useEffect, useReducer, useRef } from "react";

import type { ClarifierOutput } from "../../api/clarifier";

export type V2Stage =
  | "clarify"
  | "read_template"
  | "research_plan"
  | "gather"
  | "model_plan"
  | "model_build"
  | "draft"
  | "verify"
  | "assemble";

export type V2StreamStatus =
  | "idle"
  | "starting"
  | "running"
  | "paused"
  | "complete"
  | "failed";

export interface V2StreamState {
  status: V2StreamStatus;
  currentStage: V2Stage | null;
  completedStages: V2Stage[];
  runId: string | null;
  pausedOutput: ClarifierOutput | null;
  pausedRound: number | null;
  html: string | null;
  failedStage: V2Stage | null;
  failedReason: string | null;
}

const INITIAL: V2StreamState = {
  status: "idle",
  currentStage: null,
  completedStages: [],
  runId: null,
  pausedOutput: null,
  pausedRound: null,
  html: null,
  failedStage: null,
  failedReason: null,
};

type Action =
  | { kind: "START" }
  | { kind: "RESUME" }
  | { kind: "STOP" }
  | { kind: "RESET" }
  | { kind: "RUN_ID"; runId: string }
  | { kind: "EVENT"; event: string; data: Record<string, unknown> };

export function v2Reducer(state: V2StreamState, action: Action): V2StreamState {
  if (action.kind === "RESET") return INITIAL;
  if (action.kind === "START") return { ...INITIAL, status: "starting" };
  if (action.kind === "RESUME")
    // On resume, keep prior runId + pausedOutput visible until the first
    // new stage frame arrives, so the modal can hide gracefully.
    return { ...state, status: "starting" };
  if (action.kind === "STOP") {
    if (state.status === "complete" || state.status === "failed") return state;
    return {
      ...state,
      status: "failed",
      failedReason: "Aborted",
    };
  }
  if (action.kind === "RUN_ID")
    return { ...state, runId: action.runId };

  const { event, data } = action;
  switch (event) {
    case "stage.started": {
      const stage = data.stage as V2Stage;
      return {
        ...state,
        status: "running",
        currentStage: stage,
        // Clear paused payload once the next stage starts — guards against
        // a UI race where the modal might re-flash on resume.
        pausedOutput: null,
        pausedRound: null,
      };
    }
    case "stage.completed": {
      const stage = data.stage as V2Stage;
      return {
        ...state,
        completedStages: state.completedStages.includes(stage)
          ? state.completedStages
          : [...state.completedStages, stage],
      };
    }
    case "clarifier.pause": {
      const output = data.output as unknown as ClarifierOutput;
      const round = Number(data.round ?? 1);
      const runId = String(data.run_id ?? state.runId ?? "");
      return {
        ...state,
        status: "paused",
        currentStage: null,
        runId,
        pausedOutput: output,
        pausedRound: round,
      };
    }
    case "completed": {
      const html = String(data.html ?? "");
      const runId = String(data.run_id ?? state.runId ?? "");
      return {
        ...state,
        status: "complete",
        runId,
        html,
      };
    }
    case "failed": {
      const reason = String(data.reason ?? "Unknown failure");
      const stage = (data.stage as V2Stage | undefined) ?? null;
      const runId = String(data.run_id ?? state.runId ?? "");
      return {
        ...state,
        status: "failed",
        runId,
        failedStage: stage,
        failedReason: reason,
      };
    }
    default:
      return state;
  }
}

export interface StartOptions {
  url: string;
  body: unknown;
}

export interface ResumeOptions {
  runId: string;
  answers: {
    warning_actions: Record<string, string>;
    clarifications: Record<string, string>;
    question_answers: Record<string, string>;
  };
}

export function useV2ReportStream() {
  const [state, dispatch] = useReducer(v2Reducer, INITIAL);
  const abortRef = useRef<AbortController | null>(null);
  const lastStartRef = useRef<StartOptions | null>(null);

  const start = useCallback((opts: StartOptions) => {
    abortRef.current?.abort();
    lastStartRef.current = opts;
    dispatch({ kind: "START" });
    const controller = new AbortController();
    abortRef.current = controller;
    void consume({
      url: opts.url,
      body: opts.body,
      signal: controller.signal,
      onRunId: (runId) => dispatch({ kind: "RUN_ID", runId }),
      onEvent: (event, data) => dispatch({ kind: "EVENT", event, data }),
      onError: (message) =>
        dispatch({
          kind: "EVENT",
          event: "failed",
          data: { reason: message, run_id: null },
        }),
    });
  }, []);

  const resume = useCallback((opts: ResumeOptions) => {
    abortRef.current?.abort();
    dispatch({ kind: "RESUME" });
    const controller = new AbortController();
    abortRef.current = controller;
    void consume({
      url: `/api/departments/equity-research/v2/runs/${opts.runId}/resume`,
      body: opts.answers,
      signal: controller.signal,
      onRunId: (runId) => dispatch({ kind: "RUN_ID", runId }),
      onEvent: (event, data) => dispatch({ kind: "EVENT", event, data }),
      onError: (message) =>
        dispatch({
          kind: "EVENT",
          event: "failed",
          data: { reason: message, run_id: opts.runId },
        }),
    });
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ kind: "STOP" });
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    lastStartRef.current = null;
    dispatch({ kind: "RESET" });
  }, []);

  const retry = useCallback(() => {
    const opts = lastStartRef.current;
    if (!opts) return;
    start(opts);
  }, [start]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  return { state, start, resume, stop, reset, retry };
}

interface ConsumeArgs {
  url: string;
  body: unknown;
  signal: AbortSignal;
  onRunId: (runId: string) => void;
  onEvent: (event: string, data: Record<string, unknown>) => void;
  onError: (message: string) => void;
}

async function consume({
  url,
  body,
  signal,
  onRunId,
  onEvent,
  onError,
}: ConsumeArgs) {
  try {
    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "content-type": "application/json",
        accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) {
      onError(`v2 report stream HTTP ${res.status}`);
      return;
    }
    const runId = res.headers.get("x-run-id");
    if (runId) onRunId(runId);

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
          console.warn(`malformed v2 SSE frame for ${event}`, err, data);
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
