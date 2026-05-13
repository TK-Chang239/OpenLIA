"""Registry of internal LLM consumers ("system roles") that need an admin-
assigned model. Each role is a slot in `llm_slot_defaults` with
`slot_kind='system_role'` and `slot_id` equal to the SystemRole value.
"""

from __future__ import annotations

from enum import StrEnum


class SystemRole(StrEnum):
    AI_REVIEW = "ai_review"
    CONNECTOR_AGENTIC_RESOLVER = "connector_agentic_resolver"
    CONNECTOR_SPEC_ADAPTER = "connector_spec_adapter"
    GRAPH_EXTRACTION = "graph_extraction"
    GRAPH_SUMMARIZATION = "graph_summarization"


SYSTEM_ROLE_IDS: tuple[str, ...] = tuple(r.value for r in SystemRole)


_LABELS: dict[str, str] = {
    SystemRole.AI_REVIEW.value: "Wizard AI review",
    SystemRole.CONNECTOR_AGENTIC_RESOLVER.value: "Connector agentic resolver",
    SystemRole.CONNECTOR_SPEC_ADAPTER.value: "Connector spec adapter",
    SystemRole.GRAPH_EXTRACTION.value: "Graph memory extraction",
    SystemRole.GRAPH_SUMMARIZATION.value: "Graph memory summarization",
}


def get_system_role_label(role_id: str) -> str:
    return _LABELS[role_id]
