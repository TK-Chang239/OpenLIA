"""Stage 3: Research planner.

Reads composer inputs, template, and clarifier answers; emits a Plan with
research_strands, the frozen required_artifacts list (template + composer),
section DAG, and any slipped_requests the planner could not map.

See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §2.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.schemas.plan import (
    ArtifactSpec,
    Plan,
    ResearchStrand,
)

_SYSTEM_PROMPT = """
You are the research planner. Read the composer inputs, the selected template,
and the clarifier answers. Emit a Plan as JSON.

The Plan must include:
- research_strands: list of {id, purpose, allowed_tools}. Each strand is a
  bounded subagent. allowed_tools is the whitelist drawn from registered
  connector adapters in the format "<adapter>.<tool>" (e.g.
  "eodhd.get_fundamentals_data").
- required_artifacts: parse the composer prompt for artifact requests
  (charts, tables, sensitivity grids, etc.) and emit one ArtifactSpec per.
  Template-declared required_artifacts will be merged by the caller; do
  NOT duplicate them here.
- section_dag: {section_id: [predecessor_section_ids]} reflecting the
  template's section ordering and any dependencies.
- slipped_requests: list of composer intents you cannot map to any supported
  capability/tool/library. Use this list to surface things rather than
  silently dropping them.
""".strip()


def build_research_planner_prompt() -> str:
    return _SYSTEM_PROMPT


def _to_artifact_spec(value: Any, default_source: str) -> ArtifactSpec:
    """Convert dict or template-side ArtifactSpec into plan-side ArtifactSpec."""
    if isinstance(value, ArtifactSpec):
        return value
    if isinstance(value, dict):
        payload = dict(value)
        payload.setdefault("source", default_source)
        return ArtifactSpec.model_validate(payload)
    # Duck-type pydantic model from template_v2.spec — same field layout.
    if hasattr(value, "model_dump"):
        payload = value.model_dump()
        payload.setdefault("source", default_source)
        return ArtifactSpec.model_validate(payload)
    raise TypeError(f"cannot coerce {type(value).__name__} to ArtifactSpec")


class ResearchPlanner:
    def __init__(self, llm) -> None:
        self._llm = llm

    def plan(
        self,
        composer_inputs: dict[str, Any],
        template_spec,
        clarifier_answers: dict[str, Any],
    ) -> Plan:
        sys = build_research_planner_prompt()
        template_payload: Any
        if hasattr(template_spec, "model_dump"):
            try:
                template_payload = template_spec.model_dump()
            except Exception:
                template_payload = {}
        else:
            template_payload = {}
        user = {
            "composer_inputs": composer_inputs,
            "template": template_payload,
            "clarifier_answers": clarifier_answers,
        }
        raw = self._llm.call(system=sys, user=user)

        composer_artifacts = [
            _to_artifact_spec(a, default_source="composer")
            for a in raw.get("required_artifacts", [])
        ]
        template_artifacts = [
            _to_artifact_spec(a, default_source="template")
            for a in getattr(template_spec, "required_artifacts", [])
        ]
        # Template-side artifacts must carry source="template" regardless of
        # what the source attribute defaulted to upstream.
        for a in template_artifacts:
            if a.source != "template":
                a.source = "template"

        all_required = template_artifacts + composer_artifacts

        return Plan(
            research_strands=[
                ResearchStrand(**s) if isinstance(s, dict) else s
                for s in raw.get("research_strands", [])
            ],
            required_artifacts=all_required,
            optional_artifacts=[],
            section_dag=raw.get("section_dag", {}),
            slipped_requests=raw.get("slipped_requests", []),
        )
