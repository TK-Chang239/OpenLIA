import type { EuEvent } from "../../../api/earnings-update";

export type EuPhaseKey = "connect" | "research" | "write" | "finalize";
export type PipState = "pending" | "active" | "done";

export interface EuPhase {
  phaseKey: EuPhaseKey;
  labelKey: string;
  monoCode: string;
  pips: Record<EuPhaseKey, PipState>;
}

export const PHASE_ORDER: EuPhaseKey[] = ["connect", "research", "write", "finalize"];

const LABEL_KEYS: Record<EuPhaseKey, string> = {
  connect: "earnings.feed.gen.phase_connect",
  research: "earnings.feed.gen.phase_research",
  write: "earnings.feed.gen.phase_write",
  finalize: "earnings.feed.gen.phase_finalize",
};

/**
 * Derive the current generating phase from the rolling SSE event list.
 *
 * Phase index is monotonic (max reached), but `monoCode` reflects the
 * latest meaningful event. Output tools (write_section/emit_chart) map
 * to the write phase; set_cover/finalize map to finalize; every other
 * tool call is treated as a research/data fetch.
 */
export function deriveEuPhase(events: EuEvent[]): EuPhase {
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
        const summary = (event.payload.args_summary as string | undefined)?.trim();
        monoCode = summary || tool || monoCode;
      }
    } else if (event.type === "section.written") {
      phaseIdx = Math.max(phaseIdx, 2);
      monoCode = String(event.payload.title ?? "section");
    }
  }

  const phaseKey = PHASE_ORDER[phaseIdx];
  const pips = {} as Record<EuPhaseKey, PipState>;
  PHASE_ORDER.forEach((key, i) => {
    pips[key] = i < phaseIdx ? "done" : i === phaseIdx ? "active" : "pending";
  });

  return { phaseKey, labelKey: LABEL_KEYS[phaseKey], monoCode, pips };
}
