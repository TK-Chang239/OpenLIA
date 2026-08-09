/**
 * V3GeneratingCockpit — the live "what is the engine doing right now" strip
 * shown inside the generating V3ReportCard, above the activity feed.
 *
 * Mirrors the Morning Briefing / Earnings Update generating cards (scan line,
 * a phase line with a spinner + mono code, a sweep progress bar) so the three
 * streaming experiences share one visual language. Because v3 is adaptive —
 * it does not pre-declare a fixed section count — the progress bar is an
 * honest *indeterminate* sweep rather than a fake N-of-M fill.
 *
 * Consumes only fields already present on the live stream; no new data.
 */
import { type JSX } from "react";

import type { V3CardLive } from "./V3ReportCard";

interface PhaseInfo {
  label: string;
  code: string;
}

// V3Event.payload is Record<string, unknown>, so coerce each field.
function field(payload: Record<string, unknown>, key: string): string {
  const raw = payload[key];
  return typeof raw === "string" ? raw.replace(/[_.]+/g, " ").trim() : "";
}

function derivePhase(live: V3CardLive): PhaseInfo {
  if (live.status === "completed") return { label: "Assembling report", code: "Finalizing" };
  if (live.status === "failed") return { label: "Run failed", code: "Error" };
  if (live.status === "cancelled") return { label: "Run cancelled", code: "Stopped" };

  // Streaming: describe the most recent meaningful event.
  for (let i = live.events.length - 1; i >= 0; i--) {
    const e = live.events[i];
    switch (e.type) {
      case "tool.called":
        return { label: "Researching", code: field(e.payload, "tool_name") || "Tool" };
      case "tool.completed":
        return { label: "Analyzing results", code: field(e.payload, "tool_name") || "Tool" };
      case "section.written":
        return { label: "Drafting section", code: field(e.payload, "section_id") || "Section" };
      case "chart.emitted":
        return { label: "Building chart", code: field(e.payload, "chart_id") || "Chart" };
      case "run.started":
        return { label: "Initializing", code: field(e.payload, "model") || "Model" };
      default:
        break;
    }
  }
  return { label: "Starting run", code: "Initializing" };
}

export function V3GeneratingCockpit({ live }: { live: V3CardLive }): JSX.Element {
  const phase = derivePhase(live);
  const streaming = live.status === "streaming";
  const stalled = live.status === "failed" || live.status === "cancelled";

  return (
    <div data-testid="er-v3-cockpit" className="px-[18px] pb-[12px]">
      <div className="flex items-center gap-2.5 min-h-[20px]">
        {streaming ? (
          <span
            aria-hidden="true"
            className="h-[13px] w-[13px] flex-shrink-0 rounded-full border-[1.6px] border-[--color-border-strong] border-t-[--color-accent-primary] motion-safe:animate-spin"
          />
        ) : null}
        <span className="text-[13px] font-medium text-[--color-text-primary]">
          {phase.label}
        </span>
        {phase.code ? (
          <span className="truncate max-w-[280px] border-l border-[--color-border-subtle] pl-2.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-feedback-success]">
            {phase.code}
          </span>
        ) : null}
      </div>

      <div
        aria-hidden="true"
        className="relative mt-2.5 h-[3px] overflow-hidden rounded-full bg-[--color-surface-active]"
      >
        {streaming ? (
          <span
            data-testid="er-v3-cockpit-sweep"
            className="absolute inset-y-0 w-[32%] motion-safe:animate-lcg-sweep"
            style={{
              background:
                "linear-gradient(90deg, rgba(var(--color-accent-primary-rgb),0), rgba(var(--color-accent-primary-rgb),0.9), rgba(var(--color-accent-primary-rgb),0))",
            }}
          />
        ) : (
          <span
            className={`absolute inset-0 ${stalled ? "bg-[--color-border-strong]" : "bg-[--color-accent-primary]"}`}
          />
        )}
      </div>
    </div>
  );
}
