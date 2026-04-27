"""Quick-tier `ScopeLLMClient` driving the user's configured Quick LLM.

Resolves a model row from `SQLModelRegistry` for tier=QUICK, builds an
adapter via `build_adapter`, and invokes `adapter.generate` with a
deterministic prompt built from the `ScopeRequest`.
"""

from __future__ import annotations

import json

from openlia.connectors.scope import ScopeLLMClient, ScopeRequest
from openlia.llm.adapters import build_adapter
from openlia.llm.capabilities import capabilities_for
from openlia.llm.types import LLMRequest, Message, ModelTier
from sqlalchemy.orm import Session

from openlia_server.services.llm_registry import SQLModelRegistry


class NoQuickTierConfigured(RuntimeError):
    """Raised when no model is registered for ModelTier.QUICK."""


_PROMPT_INSTRUCTIONS = (
    "You assign each tool to zero or more departments based on prose data requirements. "
    "Each tool's domain (its name and description) is matched against each department's "
    "prose description for the connector's category. Be conservative — only assign a tool "
    "to a department if its purpose clearly serves that department's stated needs. "
    "Return ONLY a JSON object of the shape "
    '{"assignments": [{"tool_name": str, "department_ids": [str]}]}. '
    "Include every tool exactly once. department_ids may be empty."
)


def _build_prompt(req: ScopeRequest) -> str:
    tools_blob = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in req.tools
    ]
    departments_blob = [
        {"department_id": dep_id, "description": req.eligible_requirements[dep_id]}
        for dep_id in req.eligible_department_ids
    ]
    return (
        f"{_PROMPT_INSTRUCTIONS}\n\n"
        f"Connector category: {req.category.value}\n"
        f"Departments:\n{json.dumps(departments_blob, indent=2)}\n\n"
        f"Tools:\n{json.dumps(tools_blob, indent=2)}\n"
    )


class QuickTierScopeClient(ScopeLLMClient):
    """Real ScopeLLMClient backed by the user-configured Quick tier."""

    def __init__(self, session: Session, *, max_tokens: int = 4096) -> None:
        self._session = session
        self._max_tokens = max_tokens

    async def call(self, req: ScopeRequest) -> str:
        registry = SQLModelRegistry(self._session)
        row = registry.get_tier_default(ModelTier.QUICK) or registry.get_any_in_tier(
            ModelTier.QUICK
        )
        if row is None:
            raise NoQuickTierConfigured("No model configured for tier=QUICK")
        adapter = build_adapter(
            kind=row.provider_kind,
            credentials=row.credentials,
            model=row.model_ref,
            capabilities=capabilities_for(
                provider_kind=row.provider_kind,
                model=row.model_ref,
                override=row.capability_override,
            ),
        )
        prompt = _build_prompt(req)
        response = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content=prompt)],
                max_tokens=self._max_tokens,
            )
        )
        return response.content
