"""Stage 7 Drafter — DAG-ordered per-section drafting with trigger_when evaluation (Task P6).

Sections are drafted in topological order based on their depends_on graph.
Sections with a trigger_when condition are passed to TriggerEvaluator first;
if fire=False the section is SKIPPED and its output is recorded so descendants
can see "<SKIPPED: reason>" in their deps_markdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.pipeline.trigger_evaluator import TriggerEvaluator
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool

_RESEARCH_POOL_INDEX_PREFIX_LEN = 160


@dataclass
class SectionOutput:
    section_id: str
    section_name: str
    status: str  # "OK" | "SKIPPED" | "DEGRADED"
    blocks: list = field(default_factory=list)
    skip_reason: str | None = None
    degraded_reason: str | None = None


def topological_order(dag: dict[str, list[str]]) -> list[str]:
    """Return nodes in topological order using Kahn's algorithm.

    dag keys are section ids; values are lists of predecessor (dependency) ids.
    Nodes that appear only as predecessors (not as keys) are automatically
    included at the front.
    """
    # Collect every node mentioned anywhere
    all_nodes: set[str] = set(dag.keys())
    for preds in dag.values():
        all_nodes.update(preds)

    # Build adjacency: predecessor → successors
    successors: dict[str, list[str]] = {n: [] for n in all_nodes}
    in_degree: dict[str, int] = {n: 0 for n in all_nodes}

    for node, preds in dag.items():
        for pred in preds:
            successors[pred].append(node)
            in_degree[node] += 1

    # Start with nodes that have no incoming edges
    queue: list[str] = sorted(n for n, d in in_degree.items() if d == 0)
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for succ in successors[node]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    return result


class SectionDrafter:
    """Draft all sections in a template, walking the DAG in topological order."""

    def __init__(self, llm: Any, trigger_evaluator: TriggerEvaluator) -> None:
        self._llm = llm
        self._trigger_evaluator = trigger_evaluator

    def draft_all(
        self,
        sections: list[Any],
        dag: dict[str, list[str]],
        composer_inputs: dict[str, Any],
        research_pool: ResearchPool,
        model_artifacts: list[Any],
    ) -> list[SectionOutput]:
        sections_by_id: dict[str, Any] = {s.id: s for s in sections}
        order = topological_order(dag)

        # Build research_pool_index: strand → first 160 chars of findings
        research_pool_index: dict[str, str] = {
            strand: findings[:_RESEARCH_POOL_INDEX_PREFIX_LEN]
            for strand, findings in research_pool.findings_by_strand.items()
        }

        # Build model_artifacts_index: artifact_id → description
        model_artifacts_index: dict[str, str] = {}
        for art in model_artifacts:
            art_id = getattr(art, "id", None) or art.get("id", "")
            description = getattr(art, "description", None) or art.get("description", "")
            model_artifacts_index[art_id] = description

        completed: dict[str, SectionOutput] = {}

        for section_id in order:
            if section_id not in sections_by_id:
                # predecessor-only node; skip
                continue
            section = sections_by_id[section_id]

            # Build deps_markdown from completed predecessor outputs
            deps_md: dict[str, str] = {}
            for pred_id in section.depends_on or []:
                pred_out = completed.get(pred_id)
                if pred_out is None:
                    deps_md[pred_id] = "<NOT_DRAFTED>"
                elif pred_out.status == "SKIPPED":
                    deps_md[pred_id] = f"<SKIPPED: {pred_out.skip_reason}>"
                else:
                    # Serialize blocks as simple string representation
                    deps_md[pred_id] = str(pred_out.blocks)

            # Evaluate trigger_when if present
            if section.trigger_when:
                trigger_result = self._trigger_evaluator.evaluate(
                    condition=section.trigger_when,
                    composer_inputs=composer_inputs,
                    deps_markdown=deps_md,
                    research_pool_index=research_pool_index,
                    model_artifacts_index=model_artifacts_index,
                )
                if not trigger_result.fire:
                    out = SectionOutput(
                        section_id=section.id,
                        section_name=section.name,
                        status="SKIPPED",
                        skip_reason=trigger_result.reason,
                    )
                    completed[section_id] = out
                    continue

            out = self._draft_one(
                section=section,
                composer_inputs=composer_inputs,
                research_pool=research_pool,
                model_artifacts=model_artifacts,
                deps_md=deps_md,
            )
            completed[section_id] = out

        return list(completed.values())

    def _draft_one(
        self,
        section: Any,
        composer_inputs: dict[str, Any],
        research_pool: ResearchPool,
        model_artifacts: list[Any],
        deps_md: dict[str, str],
    ) -> SectionOutput:
        system = f"Draft section '{section.name}'. Directive: {section.directive}"
        user: dict[str, Any] = {
            "composer_inputs": composer_inputs,
            "research_pool_findings": research_pool.findings_by_strand,
            "model_artifacts": model_artifacts,
            "depends_on_outputs": deps_md,
        }
        try:
            raw: dict[str, Any] = self._llm.call(system=system, user=user)
            return SectionOutput(
                section_id=section.id,
                section_name=section.name,
                status="OK",
                blocks=raw.get("blocks", []),
            )
        except Exception as e:
            return SectionOutput(
                section_id=section.id,
                section_name=section.name,
                status="DEGRADED",
                degraded_reason=str(e),
            )

    def redraft_with_feedback(
        self,
        section_id: str,
        blockers: list[Any],
        retry_context: dict[str, Any],
    ) -> list[Any]:
        """Redraft a section given a list of VerifierIssue blockers and retry context.

        Called by the P7 verifier's retry loop. Returns new block list.
        """
        raw: dict[str, Any] = self._llm.call(
            system="Redraft per these issues",
            user={
                "section_id": section_id,
                "blockers": [b.model_dump() for b in blockers],
                "retry_context": retry_context,
            },
        )
        return raw.get("blocks", [])
