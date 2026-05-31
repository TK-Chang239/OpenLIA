/**
 * V3ActivityFeed — the in-card activity timeline shown while a v3 run
 * streams. Replaces the old raw StreamPanel event log: it leads with
 * the most recent few events as a quiet mono timeline and offers a
 * "Show all activity" disclosure for the full history.
 */
import { ChevronDown } from "lucide-react";
import { type JSX, useState } from "react";

import type { V3Event } from "../../api/equity-research-v3";

const COLLAPSED_CAP = 6;

export function V3ActivityFeed({ events }: { events: V3Event[] }): JSX.Element {
  const [expanded, setExpanded] = useState(false);

  // Chronological order (oldest -> newest) so the newest row sits at
  // the bottom, nearest the composer, like a chat transcript.
  const ordered = events;
  const visible = expanded ? ordered : ordered.slice(-COLLAPSED_CAP);
  const hiddenCount = ordered.length - visible.length;

  return (
    <div data-testid="er-v3-activity-feed" className="px-[18px] pb-[14px]">
      {ordered.length === 0 ? (
        <p className="m-0 font-mono text-[11px] text-[--color-text-tertiary]">
          Starting run…
        </p>
      ) : (
        <ol className="m-0 flex list-none flex-col gap-[5px] p-0">
          {visible.map((e, idx) => (
            <li
              key={ordered.length - visible.length + idx}
              data-testid="er-v3-activity-row"
              className="flex items-baseline gap-[8px] font-mono text-[11px] leading-[1.5] text-[--color-text-secondary] motion-safe:animate-[cardIn_240ms_var(--ease-out)]"
            >
              <span className="text-[--color-feedback-success]">
                {humanizeType(e.type)}
              </span>
              <span className="truncate text-[--color-text-tertiary]">
                {summarizePayload(e)}
              </span>
            </li>
          ))}
        </ol>
      )}

      {ordered.length > COLLAPSED_CAP ? (
        <button
          type="button"
          data-testid="er-v3-activity-toggle"
          onClick={() => setExpanded((v) => !v)}
          className="mt-[8px] inline-flex items-center gap-[4px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary] hover:text-[--color-text-secondary]"
        >
          <ChevronDown
            size={11}
            strokeWidth={2}
            className={expanded ? "rotate-180 transition-transform" : "transition-transform"}
            aria-hidden="true"
          />
          {expanded ? "Show less" : `Show all activity (${hiddenCount} more)`}
        </button>
      ) : null}
    </div>
  );
}

function humanizeType(type: V3Event["type"]): string {
  return type.replace(/\./g, " · ");
}

export function summarizePayload(event: V3Event): string {
  switch (event.type) {
    case "run.started":
      return `${event.payload.subject} — ${event.payload.model}`;
    case "tool.called":
      return `turn ${event.payload.turn} → ${event.payload.tool_name}`;
    case "tool.completed": {
      const ok = event.payload.ok ? "ok" : "error";
      const sid = event.payload.source_id ? ` ${event.payload.source_id}` : "";
      return `turn ${event.payload.turn} ← ${event.payload.tool_name} (${ok})${sid}`;
    }
    case "section.written":
      return `${event.payload.section_id} (${event.payload.char_count ?? "?"} chars)`;
    case "chart.emitted":
      return `${event.payload.chart_id} (${event.payload.chart_type})`;
    case "run.completed":
    case "run.failed":
    case "run.cancelled":
      return `${event.payload.section_count ?? 0} sections · ${event.payload.chart_count ?? 0} charts · ${event.payload.citation_count ?? 0} citations`;
    case "run.snapshot":
      return `prior run status: ${event.payload.status}`;
    default:
      return "";
  }
}
