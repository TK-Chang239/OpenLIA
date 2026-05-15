import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { ChevronDown, ChevronUp, Terminal, Trash2 } from "lucide-react";

import {
  type DevEvent,
  isDevModeEnabled,
  streamDevEvents,
} from "../../api/devEvents";
import morningBriefingBacklog from "./backlog/morning-briefing.md?raw";

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
  "report.request": "text-blue-500",
  "report.tool_call": "text-purple-500",
  "report.tool_result": "text-green-500",
  "report.complete": "text-yellow-600",
  "report.error": "text-red-500",
  "slim.summary": "text-amber-500",
  "expand_tools.request": "text-fuchsia-500",
  "expand_tools.result": "text-fuchsia-500",
  "expand_tools.directive_fired": "text-orange-500",
  "escalation_cache.summary": "text-amber-500",
  "escalation_cache.evict": "text-amber-600",
  "payload.stub": "text-teal-500",
  "read_payload.call": "text-teal-500",
  "read_payload.result": "text-teal-600",
  "writing.read_payload": "text-teal-500",
  "writing.forced_submit": "text-orange-500",
  "attachment.warning": "text-amber-500",
};

const BACKLOGS: Record<string, { title: string; source: string }> = {
  "/morning-briefing": {
    title: "Morning Briefing",
    source: morningBriefingBacklog,
  },
};

type Tab = "events" | "backlog";

export function DevPanel(): JSX.Element | null {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("events");
  const [events, setEvents] = useState<DevEvent[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  const backlog = useMemo(() => {
    for (const [prefix, entry] of Object.entries(BACKLOGS)) {
      if (location.pathname.startsWith(prefix)) return entry;
    }
    return null;
  }, [location.pathname]);

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
        return next.length > 500 ? next.slice(next.length - 500) : next;
      });
    });
    return close;
  }, [enabled]);

  useEffect(() => {
    if (!open || tab !== "events") return;
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [events, open, tab]);

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
          Dev panel
        </span>
        {open ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
      </button>
      {open ? (
        <>
          <div className="flex items-center justify-between border-t border-border-subtle px-2 py-1">
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => setTab("events")}
                className={`rounded px-2 py-0.5 text-[11px] font-mono uppercase ${
                  tab === "events"
                    ? "bg-surface-hover text-text-primary"
                    : "text-text-tertiary hover:text-text-primary"
                }`}
                data-testid="dev-panel-tab-events"
              >
                Events ({events.length})
              </button>
              <button
                type="button"
                onClick={() => setTab("backlog")}
                className={`rounded px-2 py-0.5 text-[11px] font-mono uppercase ${
                  tab === "backlog"
                    ? "bg-surface-hover text-text-primary"
                    : "text-text-tertiary hover:text-text-primary"
                }`}
                data-testid="dev-panel-tab-backlog"
              >
                Backlog
              </button>
            </div>
            {tab === "events" ? (
              <button
                type="button"
                onClick={() => setEvents([])}
                aria-label="Clear events"
                className="rounded p-1 text-text-tertiary hover:bg-surface-hover hover:text-text-primary"
              >
                <Trash2 size={11} />
              </button>
            ) : null}
          </div>
          {tab === "events" ? (
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
                    <div
                      className="ml-[68px] truncate text-text-primary"
                      title={e.message}
                    >
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
          ) : (
            <div
              className="max-h-[60vh] min-h-[120px] overflow-y-auto px-3 py-2 text-[12px] leading-snug"
              data-testid="dev-panel-backlog"
            >
              {backlog ? (
                <div className="prose prose-sm prose-invert max-w-none [&_h1]:mt-0 [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-xs [&_h3]:uppercase [&_h3]:tracking-wide [&_h3]:text-text-tertiary [&_pre]:overflow-x-auto [&_code]:break-words">
                  <ReactMarkdown>{backlog.source}</ReactMarkdown>
                </div>
              ) : (
                <div className="px-1 py-3 text-center text-text-tertiary">
                  No backlog for this page.
                </div>
              )}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
