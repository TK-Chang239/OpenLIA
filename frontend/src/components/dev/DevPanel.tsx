import { useEffect, useRef, useState } from "react";
import type { JSX } from "react";
import { ChevronDown, ChevronUp, Terminal, Trash2 } from "lucide-react";

import {
  type DevEvent,
  isDevModeEnabled,
  streamDevEvents,
} from "../../api/devEvents";

const CATEGORY_COLOR: Record<string, string> = {
  "chat.request": "text-blue-500",
  "chat.event": "text-text-secondary",
  "chat.tool_call": "text-purple-500",
  "chat.tool_result": "text-green-500",
  "chat.error": "text-red-500",
  "chat.done": "text-yellow-600",
  "llm.resolved": "text-cyan-500",
  "llm.call.start": "text-indigo-500",
  "llm.call.done": "text-emerald-500",
  "llm.call.error": "text-red-500",
};

export function DevPanel(): JSX.Element | null {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<DevEvent[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    isDevModeEnabled().then((v) => {
      if (!cancelled) setEnabled(v);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const close = streamDevEvents((e) => {
      setEvents((prev) => {
        const next = [...prev, e];
        // Cap on the client so the panel doesn't grow unbounded.
        return next.length > 500 ? next.slice(next.length - 500) : next;
      });
    });
    return close;
  }, [enabled]);

  useEffect(() => {
    if (!open) return;
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [events, open]);

  if (!enabled) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-40 flex w-[360px] flex-col rounded-md border border-border-subtle bg-bg-elevated shadow-lg"
      data-testid="dev-panel"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between gap-2 px-3 py-2 text-xs font-mono uppercase text-text-secondary hover:bg-surface-hover"
      >
        <span className="flex items-center gap-2">
          <Terminal size={12} aria-hidden />
          Dev events ({events.length})
        </span>
        {open ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
      </button>
      {open ? (
        <>
          <div className="flex items-center justify-end border-t border-border-subtle px-2 py-1">
            <button
              type="button"
              onClick={() => setEvents([])}
              aria-label="Clear events"
              className="rounded p-1 text-text-tertiary hover:bg-surface-hover hover:text-text-primary"
            >
              <Trash2 size={11} />
            </button>
          </div>
          <div
            ref={listRef}
            className="max-h-[40vh] min-h-[120px] overflow-y-auto px-2 py-1 font-mono text-[11px] leading-tight"
          >
            {events.length === 0 ? (
              <div className="px-1 py-3 text-center text-text-tertiary">
                Waiting for backend events…
              </div>
            ) : (
              events.map((e) => (
                <div key={e.seq} className="mb-1.5">
                  <div className="flex items-baseline gap-2">
                    <span className="text-text-tertiary">
                      {e.ts.slice(11, 23)}
                    </span>
                    <span
                      className={
                        CATEGORY_COLOR[e.category] ?? "text-text-secondary"
                      }
                    >
                      {e.category}
                    </span>
                  </div>
                  <div className="ml-[68px] truncate text-text-primary" title={e.message}>
                    {e.message}
                  </div>
                  {Object.keys(e.payload).length > 0 ? (
                    <pre
                      className="ml-[68px] mt-0.5 whitespace-pre-wrap break-all text-[10px] text-text-tertiary"
                      title={JSON.stringify(e.payload, null, 2)}
                    >
                      {JSON.stringify(e.payload)}
                    </pre>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
