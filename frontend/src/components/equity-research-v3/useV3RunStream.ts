/**
 * useV3RunStream — React hook that manages the SSE lifecycle for
 * one v3 run.
 *
 * Given a ``reportId``, opens an EventSource pointed at the server's
 * ``/v3/runs/{id}/events`` endpoint, parses each frame into a typed
 * ``V3Event``, and exposes:
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
  cancelV3Run,
  v3EventsUrl,
  V3_TERMINAL_EVENT_TYPES,
  type V3Event,
  type V3EventType,
} from "../../api/equity-research-v3";

export type V3StreamStatus = "idle" | "streaming" | "completed" | "failed" | "cancelled";

export interface V3StreamState {
  status: V3StreamStatus;
  events: V3Event[];
  sectionsWritten: number;
  chartsEmitted: number;
  citationsSeen: number;
  elapsedSeconds: number | null;
  toolCallsInflight: number;
  terminalMessage: string | null;
  errorMessage: string | null;
  cancel: () => Promise<void>;
}

const TERMINAL_TO_STATUS: Record<V3EventType, V3StreamStatus | null> = {
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

export function useV3RunStream(reportId: string | null): V3StreamState {
  const [status, setStatus] = useState<V3StreamStatus>(reportId ? "streaming" : "idle");
  const [events, setEvents] = useState<V3Event[]>([]);
  const [sectionsWritten, setSectionsWritten] = useState(0);
  const [chartsEmitted, setChartsEmitted] = useState(0);
  const [citationsSeen, setCitationsSeen] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState<number | null>(null);
  const startedAtRef = useRef<number | null>(null);
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
    setCitationsSeen(0);
    setElapsedSeconds(null);
    startedAtRef.current = null;
    setToolCallsInflight(0);
    setTerminalMessage(null);
    setErrorMessage(null);

    const source = new EventSource(v3EventsUrl(reportId));
    sourceRef.current = source;

    const handler = (type: V3EventType) => (e: MessageEvent) => {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(e.data) as Record<string, unknown>;
      } catch {
        payload = { _raw: e.data };
      }
      const event: V3Event = { type, payload };
      setEvents((prev) => [...prev, event]);

      if (type === "run.started") {
        startedAtRef.current = Date.now();
        setElapsedSeconds(0);
      } else if (type === "tool.called") {
        setToolCallsInflight((n) => n + 1);
      } else if (type === "tool.completed") {
        setToolCallsInflight((n) => Math.max(0, n - 1));
        if (payload.source_id) setCitationsSeen((n) => n + 1);
      } else if (type === "section.written") {
        setSectionsWritten((n) => n + 1);
      } else if (type === "chart.emitted") {
        setChartsEmitted((n) => n + 1);
      }

      if (V3_TERMINAL_EVENT_TYPES.has(type)) {
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
        if (startedAtRef.current != null) {
          setElapsedSeconds((Date.now() - startedAtRef.current) / 1000);
        }
        // Server closes the stream after the terminal event. Close
        // explicitly here too so EventSource's default 3s reconnect
        // doesn't loop forever once the run is done.
        source.close();
      }
    };

    const eventTypes: V3EventType[] = [
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

  // Tick the elapsed clock once per second while streaming. The
  // terminal handler writes the final value; this only drives the
  // live count-up so the generating card's timer moves.
  useEffect(() => {
    if (status !== "streaming") return;
    const id = window.setInterval(() => {
      if (startedAtRef.current != null) {
        setElapsedSeconds((Date.now() - startedAtRef.current) / 1000);
      }
    }, 1000);
    return () => window.clearInterval(id);
  }, [status]);

  const cancel = useCallback(async () => {
    if (!reportId) return;
    try {
      await cancelV3Run(reportId);
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
      citationsSeen,
      elapsedSeconds,
      toolCallsInflight,
      terminalMessage,
      errorMessage,
      cancel,
    }),
    [
      cancel,
      chartsEmitted,
      citationsSeen,
      elapsedSeconds,
      errorMessage,
      events,
      sectionsWritten,
      status,
      terminalMessage,
      toolCallsInflight,
    ],
  );
}
