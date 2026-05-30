/**
 * useEuRunStream — React hook that manages the SSE lifecycle for
 * one Earnings Update v2 run.
 *
 * Given a ``reportId``, opens an EventSource pointed at the server's
 * ``/v2/runs/{id}/events`` endpoint, parses each frame into a typed
 * ``EuEvent``, and exposes:
 *
 *   - ``events``         the rolling list (most recent last)
 *   - ``status``         derived from the most recent terminal event
 *                        or "streaming" when no terminal has landed
 *   - ``sectionsWritten``  count of section.written events seen
 *   - ``chartsEmitted``    count of chart.emitted events seen
 *   - ``cancel``         async fn that POSTs to /cancel — local
 *                        teardown happens on the run.cancelled event
 *                        the server then emits
 *
 * Closes the stream on terminal event or component unmount.
 * Reconnects are NOT attempted on EventSource error — the server
 * closes cleanly when the run ends, so an error generally means a
 * real network drop and we surface that to the caller as
 * ``status='failed'`` rather than spinning.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelRun,
  runEventsUrl,
  EU_TERMINAL_EVENT_TYPES,
  type EuEvent,
  type EuEventType,
} from "../api/earnings-update";

export type EuStreamStatus = "idle" | "streaming" | "completed" | "failed" | "cancelled";

export interface EuStreamState {
  status: EuStreamStatus;
  events: EuEvent[];
  sectionsWritten: number;
  chartsEmitted: number;
  toolCallsInflight: number;
  terminalMessage: string | null;
  errorMessage: string | null;
  cancel: () => Promise<void>;
}

const TERMINAL_TO_STATUS: Record<EuEventType, EuStreamStatus | null> = {
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

export function useEuRunStream(reportId: string | null): EuStreamState {
  const [status, setStatus] = useState<EuStreamStatus>(reportId ? "streaming" : "idle");
  const [events, setEvents] = useState<EuEvent[]>([]);
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

    const source = new EventSource(runEventsUrl(reportId));
    sourceRef.current = source;

    const handler = (type: EuEventType) => (e: MessageEvent) => {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(e.data) as Record<string, unknown>;
      } catch {
        payload = { _raw: e.data };
      }
      const event: EuEvent = { type, payload };
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

      if (EU_TERMINAL_EVENT_TYPES.has(type)) {
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
        // Server closes the stream after the terminal event. Close
        // explicitly here too so EventSource's default 3s reconnect
        // doesn't loop forever once the run is done.
        source.close();
      }
    };

    const eventTypes: EuEventType[] = [
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
        // Already closed via terminal handler — nothing to do.
        return;
      }
      // Genuine network drop. Mark as failed; we don't auto-reconnect
      // because the server's terminal frame is what we trust to
      // signal "done", and a reconnect would only race the next
      // /events GET on a maybe-already-finished run.
      setStatus("failed");
      setErrorMessage("Event stream dropped — refresh to reload the run state.");
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
      await cancelRun(reportId);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
    // Local status only flips when the server's terminal frame
    // arrives. The button stays disabled in the meantime via the
    // status check on the page.
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
