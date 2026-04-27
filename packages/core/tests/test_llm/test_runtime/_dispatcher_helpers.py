"""Shared test helpers for building Dispatchers in runtime tests.

Used by `test_chat.py` and `test_cancel_streaming_grace.py` (and likely
`test_report.py` once H3.3c lands). Centralizes the FakeTransport +
PreparedConnector + Dispatcher construction so tests stay focused on
behavior rather than boilerplate.
"""

from __future__ import annotations

from typing import Any

from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.types import Category, ToolDefinition

# Provider id used for the prefixed-name convention in tests. Empty string
# means tool calls the FakeProvider emits (e.g. `stock_quote`) match
# `<empty>__<name>` against the unprefixed name the model emitted.
TEST_PROVIDER_ID = ""


class FakeTransport:
    """Minimal async transport that returns canned results per tool name."""

    def __init__(self, results: dict[str, Any] | None = None) -> None:
        self._results = results or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return self._results.get(name, {})


def build_dispatcher(
    *,
    department_id: str,
    tools: dict[str, dict[str, Any]] | None = None,
    results: dict[str, Any] | None = None,
    category: Category = Category.FINANCIAL,
    transport: Any = None,
) -> Dispatcher:
    """Build a Dispatcher with one connector exposing the given tools.

    `tools` maps unprefixed tool name -> {"description": str, "input_schema": dict}.
    Empty mapping -> a Dispatcher with no callable tools.
    `transport` overrides the default FakeTransport (e.g. for slow-tool tests).
    """
    tools = tools or {}
    if transport is None:
        transport = FakeTransport(results=results)
    connector = PreparedConnector(
        connector_id="c1",
        provider_id=TEST_PROVIDER_ID,
        transport=transport,
        tools={
            name: ToolDefinition(
                name=name,
                description=spec.get("description", ""),
                input_schema=spec.get("input_schema", {"type": "object"}),
            )
            for name, spec in tools.items()
        },
    )
    return Dispatcher(
        connectors={"c1": connector},
        allowlist={department_id: [("c1", name) for name in tools]},
        connector_categories={"c1": category},
    )
