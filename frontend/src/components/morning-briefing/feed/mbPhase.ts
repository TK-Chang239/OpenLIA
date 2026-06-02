import type { MbEvent } from "../../../api/morning-briefing";

export type MbPhaseKey = "connect" | "research" | "write" | "finalize";
export type PipState = "pending" | "active" | "done";

export interface MbPhase {
  phaseKey: MbPhaseKey;
  labelKey: string;
  monoCode: string;
  pips: Record<MbPhaseKey, PipState>;
}

export const PHASE_ORDER: MbPhaseKey[] = [
  "connect",
  "research",
  "write",
  "finalize",
];

const LABEL_KEYS: Record<MbPhaseKey, string> = {
  connect: "morning_briefing.feed.gen.phase_connect",
  research: "morning_briefing.feed.gen.phase_research",
  write: "morning_briefing.feed.gen.phase_write",
  finalize: "morning_briefing.feed.gen.phase_finalize",
};

/**
 * Coerce a tool's `args_summary` into a short display string. The backend
 * sends it as a dict (e.g. `{ query: "..." }`), not a string, so we join
 * its scalar values; a plain string is used verbatim. Anything else (or an
 * empty dict) yields "" so the caller falls back to the tool name.
 */
function argsSummaryText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return Object.values(value as Record<string, unknown>)
      .filter((v) => typeof v === "string" || typeof v === "number")
      .map(String)
      .join(" · ")
      .trim();
  }
  return "";
}

/**
 * Derive the current generating phase from the rolling SSE event list.
 *
 * Phase index is monotonic (max reached), but `monoCode` reflects the
 * latest meaningful event. Output tools (write_section/emit_chart) map to
 * the write phase; set_cover/finalize map to finalize; every other tool
 * call is treated as a research/data fetch.
 */
export function deriveMbPhase(events: MbEvent[]): MbPhase {
  let phaseIdx = 0;
  let monoCode = "RUN_STARTED";

  for (const event of events) {
    if (event.type === "tool.called") {
      const tool = String(event.payload.tool_name ?? "");
      if (tool === "set_cover" || tool === "finalize") {
        phaseIdx = Math.max(phaseIdx, 3);
        monoCode = "FINALIZING";
      } else if (tool === "write_section") {
        phaseIdx = Math.max(phaseIdx, 2);
      } else if (tool === "emit_chart") {
        phaseIdx = Math.max(phaseIdx, 2);
        monoCode = "EMIT_CHART";
      } else {
        phaseIdx = Math.max(phaseIdx, 1);
        const summary = argsSummaryText(event.payload.args_summary);
        monoCode = summary || tool || monoCode;
      }
    } else if (event.type === "section.written") {
      phaseIdx = Math.max(phaseIdx, 2);
      monoCode = String(event.payload.title ?? "section");
    }
  }

  const phaseKey = PHASE_ORDER[phaseIdx];
  const pips = {} as Record<MbPhaseKey, PipState>;
  PHASE_ORDER.forEach((key, i) => {
    pips[key] = i < phaseIdx ? "done" : i === phaseIdx ? "active" : "pending";
  });

  return { phaseKey, labelKey: LABEL_KEYS[phaseKey], monoCode, pips };
}
