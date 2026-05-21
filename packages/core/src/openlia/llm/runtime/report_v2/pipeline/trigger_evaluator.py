"""TriggerEvaluator — LLM-backed condition evaluator for conditional sections (Task P6).

Fail-open: any LLM exception returns TriggerResult(fire=True, ...) so the
section always drafts when the evaluator cannot reach a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TriggerResult:
    fire: bool
    reason: str


class TriggerEvaluator:
    """Evaluate a section's trigger_when condition against pipeline context."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def evaluate(
        self,
        condition: str,
        composer_inputs: dict[str, Any],
        deps_markdown: dict[str, str],
        research_pool_index: dict[str, str],
        model_artifacts_index: dict[str, str],
    ) -> TriggerResult:
        system = (
            "Evaluate the condition against the provided context. "
            "Return JSON {fire: bool, reason: str}."
        )
        user: dict[str, Any] = {
            "condition": condition,
            "composer_inputs": composer_inputs,
            "deps_markdown": deps_markdown,
            "research_pool_index": research_pool_index,
            "model_artifacts_index": model_artifacts_index,
        }
        try:
            raw: dict[str, Any] = self._llm.call(system=system, user=user)
            return TriggerResult(
                fire=bool(raw.get("fire", True)),
                reason=str(raw.get("reason", "")),
            )
        except Exception as e:
            return TriggerResult(fire=True, reason=f"evaluator_failed: {e}")
