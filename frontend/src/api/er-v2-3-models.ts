/**
 * v2.3 equity-research per-stage model assignment client.
 *
 * Mirrors `openlia.llm.runtime.report_v2_3.slots.LLM_V23_SLOTS` —
 * keep the SLOTS tuple in sync. VISUALIZE and ASSEMBLE are
 * deterministic and have no slot.
 */
import { request } from "./_request";

export type V23Slot =
  | "clarify"
  | "plan"
  | "research"
  | "compute"
  | "synthesize"
  | "write"
  | "verify";

export const V23_SLOTS: V23Slot[] = [
  "clarify",
  "plan",
  "research",
  "compute",
  "synthesize",
  "write",
  "verify",
];

export const V23_SLOT_LABEL: Record<V23Slot, string> = {
  clarify: "Clarify",
  plan: "Plan",
  research: "Research",
  compute: "Compute (valuation inputs)",
  synthesize: "Synthesize (thesis)",
  write: "Write (section drafter)",
  verify: "Verify",
};

export const V23_SLOT_DESCRIPTION: Record<V23Slot, string> = {
  clarify:
    "Stage 1 — reads your prompt, decides whether to ask blocking questions or proceed with stated assumptions. Suspendable.",
  plan:
    "Stage 2 — converts the prompt into an Outline with data_needs that drive RESEARCH. Sets the valuation plan.",
  research:
    "Stage 3 — autonomous tool-use loop over EODHD + web_search; accumulates BundleFacts with provenance attached at fetch time.",
  compute:
    "Stage 4 — proposes inputs (growth path, WACC, comp set) for the deterministic DCF / Comps / Sensitivity math. The model does NOT compute fair value; it picks the inputs.",
  synthesize:
    "Stage 5 — distills the bundle into one ReportThesis every writer is conditioned on. Owns chart specs and section mandates.",
  write:
    "Stage 6 — produces one section body at a time using {{CITE:fact_id}} and {{FIG:chart_id}} placeholders. Most expensive slot.",
  verify:
    "Stage 7b — surfaces coherence problems (value mismatches, redundancy, contradiction) the writer can't catch from inside a section. Routes back to WRITE on HIGH severity.",
};

/** Tier guidance per slot (small/cheap vs mid vs flagship). */
export const V23_SLOT_RECOMMENDATION: Record<V23Slot, string> = {
  clarify:
    "Cheap mini-tier is fine. One short structured-output call that lists at most three clarifying questions plus stated assumptions. No prose, no deep reasoning.",
  plan:
    "Mid-tier with solid reasoning. Decides what sections exist + what evidence each needs. Reliable structured output required.",
  research:
    "Mid-to-flagship. Drives a multi-turn tool-use loop; total tokens add up across turns. Tool-calling reliability matters more than prose quality — a strong mid-tier with good function-calling is usually the right cost/quality trade.",
  compute:
    "Mid-tier. Proposes valuation inputs with bundle fact ids; needs numeric judgment + strict adherence to the input schemas. Mini may suffice if it tracks the schema well.",
  synthesize:
    "Flagship or strong mid. Anchors the report — central argument, key takeaways, chart specs, section mandates. Coherence quality here cascades to every writer.",
  write:
    "Flagship. Section prose, citation discipline, length budgets all live here. The single biggest call per run; don't compromise.",
  verify:
    "Mid-tier. Reads drafted sections against the bundle and raises issues. Strong instruction-following but not creative writing.",
};

export interface AssignmentsResponse {
  assignments: Partial<Record<V23Slot, string>>;
  slots: V23Slot[];
  missing: V23Slot[];
}

export function getV23ModelAssignments(): Promise<AssignmentsResponse> {
  return request<AssignmentsResponse>(
    "/api/departments/equity-research/v2.3/model-assignments",
  );
}

export function putV23ModelAssignments(
  assignments: Partial<Record<V23Slot, string>>,
): Promise<AssignmentsResponse> {
  return request<AssignmentsResponse>(
    "/api/departments/equity-research/v2.3/model-assignments",
    {
      method: "PUT",
      body: JSON.stringify({ assignments }),
    },
  );
}
