/**
 * useMbRunStream — React hook that manages the SSE lifecycle for
 * one Morning Briefing run.
 *
 * Given a ``reportId``, opens an EventSource pointed at the server's
 * ``/runs/{id}/events`` endpoint, parses each frame into a typed
 * ``MbEvent``, and exposes:
 *
 *   - ``events``           the rolling list (most recent last)
 *   - ``status``           derived from the most recent terminal event
 *                          or "streaming" when no terminal has landed
 *   - ``sectionsWritten``  count of section.written events seen
 *   - ``chartsEmitted``    count of chart.emitted events seen
 *   - ``cancel``           async fn that POSTs to /cancel — local
 *                          teardown happens on the run.cancelled event
 *                          the server then emits
 *
 * Closes the stream on terminal event or component unmount.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelMbRun,
  mbRunEventsUrl,
  MB_TERMINAL_EVENT_TYPES,
  type MbEvent,
  type MbEventType,
} from "../api/morning-briefing";

export type MbStreamStatus =
  | "idle"
  | "streaming"
  | "completed"
  | "failed"
  | "cancelled";

export interface MbStreamState {
  status: MbStreamStatus;
  events: MbEvent[];
  sectionsWritten: number;
  chartsEmitted: number;
  toolCallsInflight: number;
  terminalMessage: string | null;
  errorMessage: string | null;
  cancel: () => Promise<void>;
}

const TERMINAL_TO_STATUS: Record<MbEventType, MbStreamStatus | null> = {
  "run.started": null,
  "tool.called": null,
  "tool.completed": null,
  "section.written": null,
  "chart.emitted": null,
  "run.completed": "completed",
  "run.failed": "failed",
  "run.cancelled": "cancelled",
  "run.snapshot": "completed", // refined below using payload.status
};

export function useMbRunStream(reportId: string | null): MbStreamState {
  const [status, setStatus] = useState<MbStreamStatus>(
    reportId ? "streaming" : "idle",
  );
  const [events, setEvents] = useState<MbEvent[]>([]);
  const [sectionsWritten, setSectionsWritten] = useState(0);
  const [chartsEmitted, setChartsEmitted] = useState(0);
  const [toolCallsInflight, setToolCallsInflight] = useState(0);
  const [terminalMessage, setTerminalMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!reportId) {
      setStatus("idle");
      return;
    }
    setStatus("streaming");
    setEvents([]);
    setSectionsWritten(0);
    setChartsEmitted(0);
    setToolCallsInflight(0);
    setTerminalMessage(null);
    setErrorMessage(null);

    const source = new EventSource(mbRunEventsUrl(reportId));
    sourceRef.current = source;

    const handler = (type: MbEventType) => (e: MessageEvent) => {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(e.data) as Record<string, unknown>;
      } catch {
        payload = { _raw: e.data };
      }
      const event: MbEvent = { type, payload };
      setEvents((prev) => [...prev, event]);

      if (type === "tool.called") {
        setToolCallsInflight((n) => n + 1);
      } else if (type === "tool.completed") {
        setToolCallsInflight((n) => Math.max(0, n - 1));
      } else if (type === "section.written") {
        setSectionsWritten((n) => n + 1);
      } else if (type === "chart.emitted") {
        setChartsEmitted((n) => n + 1);
      }

      if (MB_TERMINAL_EVENT_TYPES.has(type)) {
        const message = (payload.message as string | undefined) ?? null;
        setTerminalMessage(message);
        let resolved = TERMINAL_TO_STATUS[type];
        if (type === "run.snapshot") {
          const snapshotStatus = String(payload.status ?? "completed");
          resolved =
            snapshotStatus === "failed"
              ? "failed"
              : snapshotStatus === "cancelled"
                ? "cancelled"
                : "completed";
        }
        if (resolved) setStatus(resolved);
        source.close();
      }
    };

    const eventTypes: MbEventType[] = [
      "run.started",
      "tool.called",
      "tool.completed",
      "section.written",
      "chart.emitted",
      "run.completed",
      "run.failed",
      "run.cancelled",
      "run.snapshot",
    ];
    for (const t of eventTypes) {
      source.addEventListener(t, handler(t) as EventListener);
    }

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        return;
      }
      setStatus("failed");
      setErrorMessage(
        "Event stream dropped — refresh to reload the run state.",
      );
      source.close();
    };

    return () => {
      sourceRef.current = null;
      source.close();
    };
  }, [reportId]);

  const cancel = useCallback(async () => {
    if (!reportId) return;
    try {
      await cancelMbRun(reportId);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  }, [reportId]);

  return useMemo(
    () => ({
      status,
      events,
      sectionsWritten,
      chartsEmitted,
      toolCallsInflight,
      terminalMessage,
      errorMessage,
      cancel,
    }),
    [
      cancel,
      chartsEmitted,
      errorMessage,
      events,
      sectionsWritten,
      status,
      terminalMessage,
      toolCallsInflight,
    ],
  );
}
