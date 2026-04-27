"""Adapter LLM that scopes a connector's tools to departments.

The LLM client is injected so unit tests run without network. Production
binds it to the LLM resolver's quick-tier client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from openlia.connectors.types import Category, ScopedBy, ScopedTool, ToolDefinition


@dataclass(frozen=True)
class DepartmentRequirements:
    department_id: str
    per_category: dict[str, dict[str, Any]]
    """Maps Category.value -> {'required': bool, 'description': str}."""


@dataclass(frozen=True)
class ScopeRequest:
    connector_id: str
    provider_id: str
    category: Category
    tools: list[ToolDefinition]
    eligible_department_ids: list[str]
    eligible_requirements: dict[str, str]
    """department_id -> the prose description for this category."""


class ScopeLLMClient(Protocol):
    async def call(self, req: ScopeRequest) -> str: ...


def _parse(
    payload: str, valid_dep_ids: set[str], valid_tool_names: set[str]
) -> list[tuple[str, list[str]]]:
    data = json.loads(payload)
    if not isinstance(data, dict) or "assignments" not in data:
        raise ValueError("missing assignments")
    out: list[tuple[str, list[str]]] = []
    for row in data["assignments"]:
        if not isinstance(row, dict):
            raise ValueError("non-dict assignment")
        name = row.get("tool_name")
        deps = row.get("department_ids", [])
        if name not in valid_tool_names:
            continue
        if not isinstance(deps, list):
            raise ValueError(f"non-list department_ids for {name}")
        out.append((name, [d for d in deps if d in valid_dep_ids]))
    return out


async def scope_connector(
    connector_id: str,
    provider_id: str,
    category: Category,
    tools: list[ToolDefinition],
    requirements: dict[str, DepartmentRequirements],
    llm: ScopeLLMClient,
) -> list[ScopedTool]:
    eligible = {
        dep_id: r.per_category[category.value]["description"]
        for dep_id, r in requirements.items()
        if category.value in r.per_category
    }
    req = ScopeRequest(
        connector_id=connector_id,
        provider_id=provider_id,
        category=category,
        tools=tools,
        eligible_department_ids=sorted(eligible.keys()),
        eligible_requirements=eligible,
    )
    valid_dep_ids = set(eligible.keys())
    valid_tool_names = {t.name for t in tools}

    last_error: Exception | None = None
    for _attempt in range(2):
        raw = await llm.call(req)
        try:
            assignments = _parse(raw, valid_dep_ids, valid_tool_names)
        except ValueError as exc:
            last_error = exc
            continue
        result: list[ScopedTool] = []
        for tool_name, dep_ids in assignments:
            for dep in dep_ids:
                result.append(
                    ScopedTool(
                        department_id=dep,
                        connector_id=connector_id,
                        tool_name=tool_name,
                    )
                )
        return result
    raise ValueError(f"adapter LLM produced invalid output twice: {last_error!r}")


# Marker re-export so callers writing rows know which scoped_by to use.
LLM_ADAPTER_SCOPED_BY = ScopedBy.LLM_ADAPTER
