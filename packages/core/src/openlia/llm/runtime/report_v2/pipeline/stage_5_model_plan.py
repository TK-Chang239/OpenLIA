"""Stage 5: Model planner.

Reads the populated research pool and emits optional_artifacts only.
Required artifacts are frozen by stage 3 and must not be modified here.

See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §6.
"""

from __future__ import annotations

import logging

from openlia.llm.runtime.report_v2.schemas.plan import ArtifactSpec, Plan

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """
You are the model planner. Read the required artifacts and the research pool index.
Based on what the research pool contains, decide which optional artifacts would
add value to the report.

Rules:
- Emit optional_artifacts only. Do NOT touch required_artifacts.
- Each artifact must have: id, type, description. Optionally: parameters, helper,
  source_strand, target_section_id.
- Allowed type values: chart, table, kpi_strip, excel, quote_block.
- Output valid JSON with exactly one key: {"optional_artifacts": [...]}.
- If no optional artifacts are warranted, emit {"optional_artifacts": []}.
""".strip()


def build_model_planner_prompt() -> str:
    return _SYSTEM_PROMPT


class ModelPlanner:
    def __init__(self, llm) -> None:
        self._llm = llm

    def plan(self, plan: Plan, research_pool) -> Plan:
        system = build_model_planner_prompt()

        # Build research pool index: first line, first 160 chars per strand
        pool_index: dict[str, str] = {}
        for strand_id, findings in research_pool.findings_by_strand.items():
            first_line = findings.split("\n", 1)[0]
            pool_index[strand_id] = first_line[:160]

        user = {
            "required_artifacts": [a.model_dump() for a in plan.required_artifacts],
            "research_pool_index": pool_index,
        }

        try:
            raw = self._llm.call(system=system, user=user)
            raw_optionals = raw.get("optional_artifacts", [])
            optional: list[ArtifactSpec] = []
            for item in raw_optionals:
                if isinstance(item, ArtifactSpec):
                    spec = item
                elif isinstance(item, dict):
                    payload = dict(item)
                    payload.setdefault("source", "planner")
                    spec = ArtifactSpec.model_validate(payload)
                elif hasattr(item, "model_dump"):
                    payload = item.model_dump()
                    payload.setdefault("source", "planner")
                    spec = ArtifactSpec.model_validate(payload)
                else:
                    logger.warning("skipping unrecognized optional artifact type: %s", type(item))
                    continue
                if spec.source != "planner":
                    spec = spec.model_copy(update={"source": "planner"})
                optional.append(spec)
        except Exception:
            logger.exception("model planner LLM call failed; optional_artifacts defaulting to []")
            optional = []

        return plan.model_copy(update={"optional_artifacts": optional})
