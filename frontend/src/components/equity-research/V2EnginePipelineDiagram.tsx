/**
 * V2EnginePipelineDiagram — visual overview of the v2.2 pipeline so a user
 * who's about to assign per-stage models can see how those stages fit
 * together and which ones actually call an LLM.
 *
 * Rendered above the slot list inside V2EngineModelsPicker. Pure
 * presentational: takes no props and reads nothing from the network.
 *
 * Source of truth for the pipeline order: `RunnerV2.execute()` in
 * `packages/core/src/openlia/llm/runtime/report_v2/runner_v2.py`. Keep this
 * list in sync with that generator.
 */
import { type JSX } from "react";

import type { V2Slot } from "../../api/er-v2-models";
import { V2_SLOT_LABEL } from "../../api/er-v2-models";

interface StageNode {
  /** Order shown in the diagram. Matches the stage_N naming in the runner. */
  ordinal: string;
  /** Short title shown on the chip. */
  title: string;
  /** When set, this stage calls the named slot's LLM. */
  slot: V2Slot | null;
  /** Why this stage exists. Shown as a small caption under the chip. */
  caption: string;
  /** Multiplicity hint, e.g. "× strands" or "× sections". */
  parallelism?: string;
}

const STAGES: StageNode[] = [
  {
    ordinal: "0",
    title: "Load template",
    slot: null,
    caption:
      "Server loads the selected report template (sections, default artifacts, fidelity). Happens once, before any LLM stage runs; the loaded template is passed into every stage below — including Clarify.",
  },
  {
    ordinal: "1",
    title: "Clarify",
    slot: "clarifier",
    caption:
      "Reads your ticker + prompt AND the loaded template, then asks any clarifying questions before research starts.",
  },
  {
    ordinal: "2",
    title: "Plan research",
    slot: "research_planner",
    caption: "Decide which research strands to dispatch.",
  },
  {
    ordinal: "3",
    title: "Gather",
    slot: "strand_subagent",
    caption: "Run each research strand; collect findings + citations.",
    parallelism: "× strands",
  },
  {
    ordinal: "4",
    title: "Plan model",
    slot: "model_planner",
    caption: "Translate the plan into concrete artifact specs.",
  },
  {
    ordinal: "4b",
    title: "Plan helpers",
    slot: "planner_v2_2",
    caption: "Pick v2.2 library helpers + their parameters per artifact.",
  },
  {
    ordinal: "5",
    title: "Build model",
    slot: "model_builder",
    caption: "Produce each required artifact (chart, table, financial model).",
  },
  {
    ordinal: "6a",
    title: "Materialize",
    slot: null,
    caption: "Invoke the chosen helpers; collect their outputs (no LLM).",
  },
  {
    ordinal: "6b",
    title: "Draft",
    slot: "section_drafter",
    caption: "Write the report sections from the gathered evidence.",
    parallelism: "× sections",
  },
  {
    ordinal: "7",
    title: "Verify",
    slot: "llm_verifier",
    caption: "Check each section against the evidence; retry weak sections.",
  },
  {
    ordinal: "8",
    title: "Assemble",
    slot: null,
    caption: "Render the final HTML report (no LLM).",
  },
];

export function V2EnginePipelineDiagram(): JSX.Element {
  return (
    <section
      data-testid="er-v2-engine-pipeline-diagram"
      aria-label="v2.2 engine pipeline overview"
      className="rounded-[9px] border border-[--color-border-subtle] bg-[--color-bg-base] px-[14px] py-[12px]"
    >
      <header className="mb-[10px] flex items-center justify-between gap-[10px]">
        <div className="flex min-w-0 flex-col">
          <span className="font-display text-[12.5px] font-semibold text-[--color-text-primary]">
            How the engine works
          </span>
          <span className="text-[11px] leading-[1.45] text-[--color-text-secondary]">
            The template is loaded first (stage 0) and is passed into every
            stage below — so Clarify already knows the report&apos;s sections
            and artifacts when it asks its questions. After that, your run
            flows left-to-right. Solid boxes call an LLM (your chosen model
            fires there). Dashed boxes are deterministic framework steps with
            no model.
          </span>
        </div>
      </header>

      <ol className="flex flex-wrap items-stretch gap-y-[16px]">
        {STAGES.map((stage, idx) => (
          <li
            key={stage.ordinal}
            className="flex items-stretch"
          >
            <StageChip stage={stage} />
            {idx < STAGES.length - 1 ? <ArrowConnector /> : null}
          </li>
        ))}
      </ol>

      <div className="mt-[12px] flex flex-wrap items-center gap-x-[14px] gap-y-[4px] font-mono text-[9.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
        <span className="inline-flex items-center gap-[5px]">
          <span
            aria-hidden="true"
            className="inline-block h-[10px] w-[10px] rounded-[2px] border border-[--color-accent-primary] bg-[rgba(212,255,0,0.12)]"
          />
          LLM stage (slot)
        </span>
        <span className="inline-flex items-center gap-[5px]">
          <span
            aria-hidden="true"
            className="inline-block h-[10px] w-[10px] rounded-[2px] border border-dashed border-[--color-border-strong] bg-transparent"
          />
          framework stage (no LLM)
        </span>
      </div>
    </section>
  );
}

function StageChip({ stage }: { stage: StageNode }): JSX.Element {
  const isLLM = stage.slot !== null;
  return (
    <div
      className={[
        "flex min-w-[110px] max-w-[150px] flex-col gap-[3px] rounded-[7px] px-[8px] py-[6px]",
        isLLM
          ? "border border-[rgba(168,204,0,0.55)] bg-[rgba(212,255,0,0.06)]"
          : "border border-dashed border-[--color-border-strong] bg-[--color-bg-elevated]",
      ].join(" ")}
      title={stage.caption}
    >
      <div className="flex items-baseline gap-[6px]">
        <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
          {stage.ordinal}
        </span>
        <span className="truncate text-[12px] font-medium text-[--color-text-primary]">
          {stage.title}
        </span>
      </div>
      {isLLM && stage.slot ? (
        <span className="truncate font-mono text-[9.5px] uppercase tracking-[0.06em] text-[--color-accent-on]">
          slot: {stage.slot}
        </span>
      ) : (
        <span className="font-mono text-[9.5px] uppercase tracking-[0.06em] text-[--color-text-tertiary]">
          no LLM
        </span>
      )}
      <span className="text-[10.5px] leading-[1.35] text-[--color-text-secondary]">
        {V2_SLOT_LABEL_OR_NULL(stage.slot)}
        {stage.parallelism ? (
          <span className="ml-[4px] font-mono text-[9.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            {stage.parallelism}
          </span>
        ) : null}
      </span>
    </div>
  );
}

function V2_SLOT_LABEL_OR_NULL(slot: V2Slot | null): string {
  return slot ? V2_SLOT_LABEL[slot] : "deterministic";
}

function ArrowConnector(): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className="mx-[2px] flex items-center px-[2px] font-mono text-[12px] leading-none text-[--color-text-tertiary]"
    >
      →
    </span>
  );
}
