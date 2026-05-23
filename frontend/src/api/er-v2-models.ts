/**
 * v2.2 equity-research per-stage model assignment client.
 *
 * Mirrors `openlia.llm.runtime.report_v2.slots.V2Slot` — keep the SLOTS
 * tuple in sync when adding/removing pipeline stages.
 */
import { request } from "./_request";

export type V2Slot =
  | "clarifier"
  | "research_planner"
  | "strand_subagent"
  | "model_planner"
  | "planner_v2_2"
  | "model_builder"
  | "section_drafter"
  | "llm_verifier";

export const V2_SLOTS: V2Slot[] = [
  "clarifier",
  "research_planner",
  "strand_subagent",
  "model_planner",
  "planner_v2_2",
  "model_builder",
  "section_drafter",
  "llm_verifier",
];

export const V2_SLOT_LABEL: Record<V2Slot, string> = {
  clarifier: "Clarifier",
  research_planner: "Research planner",
  strand_subagent: "Research strand subagent",
  model_planner: "Model planner",
  planner_v2_2: "v2.2 planner (helper selection)",
  model_builder: "Model builder",
  section_drafter: "Section drafter",
  llm_verifier: "Verifier",
};

export const V2_SLOT_DESCRIPTION: Record<V2Slot, string> = {
  clarifier:
    "Stage 1 — reads your ticker + prompt together with the loaded report template, then asks any clarifying questions before research begins.",
  research_planner: "Stage 2 — emits the plan, including which research strands to dispatch.",
  strand_subagent:
    "Stage 3 — executes each research strand in parallel; called multiple times per run.",
  model_planner: "Stage 4 — turns the plan into concrete artifact specifications.",
  planner_v2_2: "Stage 4b — selects helpers from the v2.2 library to produce artifacts.",
  model_builder: "Stage 5 — builds each required artifact (charts, tables, models).",
  section_drafter: "Stage 6b — writes the actual report sections; most expensive slot.",
  llm_verifier: "Stage 7 — verifies the drafted sections against the gathered evidence.",
};

/** Per-slot guidance the picker surfaces under each row. Phrased in terms of
 *  the model *tier* (small/cheap vs mid vs flagship) and *capability* (good
 *  reasoning, structured-output reliable, etc.) rather than naming specific
 *  models so it stays accurate as the user adds new providers. */
export const V2_SLOT_RECOMMENDATION: Record<V2Slot, string> = {
  clarifier:
    "Cheap mini-tier is fine. The job is a short structured-output call that lists clarifying questions and capability warnings — no long-form prose, no deep reasoning. Don't burn flagship tokens here.",
  research_planner:
    "Mid-tier with solid reasoning. Emits the research strands and section DAG; thinking quality matters more than prose. Reliable structured output is required. A strong mini may suffice; flagship if you can spare it.",
  strand_subagent:
    "Cheap mini-tier — runs in parallel, once per strand, so total tokens add up fast. The current stub just summarises domain knowledge per strand; once it becomes tool-aware (Phase 0), keep it cheap and rely on multiple calls rather than one expensive call.",
  model_planner:
    "Cheap-to-mid. Translates the plan into artifact specifications; mostly bookkeeping. Mini-tier is usually enough unless your templates demand complex artifact-spec reasoning.",
  planner_v2_2:
    "Mid-to-flagship. Selects helpers from the v2.2 library and chooses their parameters; quality here directly affects which exhibits the report can render. Pick a model you trust to follow a registry-schema strictly.",
  model_builder:
    "Mid-tier. Builds each required artifact (charts/tables/financial models). Numerical correctness matters; pick a model with strong tabular and math handling, not necessarily flagship prose quality.",
  section_drafter:
    "Flagship. This is the writer — section prose quality, evidence-citation discipline, and length-budget adherence all live here. The single most-expensive call per run; don't compromise on this one.",
  llm_verifier:
    "Mid-tier. Reads drafted sections against the gathered evidence and raises issues; needs strong instruction-following but not creative writing. A capable mini is usually a good cost/quality trade.",
};

export interface AssignmentsResponse {
  assignments: Partial<Record<V2Slot, string>>;
  slots: V2Slot[];
  missing: V2Slot[];
}

export function getModelAssignments(): Promise<AssignmentsResponse> {
  return request<AssignmentsResponse>(
    "/api/departments/equity-research/v2/model-assignments",
  );
}

export function putModelAssignments(
  assignments: Partial<Record<V2Slot, string>>,
): Promise<AssignmentsResponse> {
  return request<AssignmentsResponse>(
    "/api/departments/equity-research/v2/model-assignments",
    {
      method: "PUT",
      body: JSON.stringify({ assignments }),
    },
  );
}
