"""Build a runtime `Dispatcher` from persisted Connector + RunnerCallableSpec rows.

Reads:
- `connectors` rows -> `PreparedConnector` map (keyed by connector_id).
- `runner_callable_specs` rows -> `(department_id, need_id) -> CallableSpec` map.

Per spec §8.1 the dispatcher exposes the full validated tool inventory; per
§9 it resolves runner needs by id within an `in_department(...)` context.

Phase 5 introduces the unified `CallableTransport` Protocol and the concrete
`PythonLibTransport` / MCP transport implementations. Until those land,
`_prepare_connector` instantiates a placeholder transport that fails fast
on invocation. `build_dispatcher` is therefore safe to wire up at boot but
will only succeed at `dispatch_tool_use` / `fetch_need` once Phase 5 lands.
"""

from __future__ import annotations

from typing import Any

from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.types import (
    CallableDefinition,
    CallableSpec,
    Category,
    ConnectorStatus,
    InstanceFactory,
    ParamBinding,
    ToolDefinition,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector, RunnerCallableSpec


class _UnboundTransport:
    """Placeholder transport: any call raises RuntimeError.

    Phase 5 replaces this with a `CallableTransport` chosen per `LaunchSpec`
    mode. Existing at this layer keeps `Dispatcher.candidate_tools()` usable
    (it never invokes the transport) while signalling clearly that runtime
    invocation requires Phase 5.
    """

    def __init__(self, connector_id: str) -> None:
        self._connector_id = connector_id

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise RuntimeError(
            f"connector {self._connector_id!r} has no live transport; "
            "Phase 5 (transports) has not landed yet"
        )


def _prepare_connector(row: Connector) -> PreparedConnector:
    tools: dict[str, ToolDefinition] = {}
    for entry in row.cached_tools or []:
        tools[entry["name"]] = ToolDefinition(
            name=entry["name"],
            description=entry.get("description", ""),
            input_schema=entry.get("input_schema", {}),
        )

    callables: dict[str, CallableDefinition] = {}
    for entry in row.cached_python_callables or []:
        qn = entry["qualname"]
        callables[qn] = CallableDefinition(
            qualname=qn,
            signature=entry.get("signature", ""),
            doc=entry.get("doc", ""),
        )

    return PreparedConnector(
        connector_id=row.id,
        provider_id=row.provider_id,
        category=Category(row.category),
        status=ConnectorStatus(row.status),
        transport=_UnboundTransport(row.id),
        tools=tools,
        callables=callables,
    )


def _hydrate_spec(row: RunnerCallableSpec) -> CallableSpec:
    raw = row.spec or {}
    bindings_raw = raw.get("param_bindings") or {}
    bindings: dict[str, ParamBinding] = {}
    for caller_name, binding in bindings_raw.items():
        bindings[caller_name] = ParamBinding(
            to_arg=binding["to_arg"],
            transform=binding.get("transform"),
        )

    factory_raw = raw.get("instance_factory")
    instance_factory: InstanceFactory | None = None
    if factory_raw is not None:
        instance_factory = InstanceFactory(
            cls=factory_raw["cls"],
            args=dict(factory_raw.get("args") or {}),
        )

    return CallableSpec(
        need_id=row.need_id,
        access_mode=row.access_mode,  # type: ignore[arg-type]
        tool_name=raw.get("tool_name"),
        module=raw.get("module"),
        instance_factory=instance_factory,
        method=raw.get("method"),
        param_bindings=bindings,
        constants=dict(raw.get("constants") or {}),
        shape=raw.get("shape", "any"),
    )


def build_dispatcher(session: Session) -> Dispatcher:
    connector_rows = session.execute(select(Connector)).scalars().all()
    spec_rows = session.execute(select(RunnerCallableSpec)).scalars().all()

    prepared = {row.id: _prepare_connector(row) for row in connector_rows}
    specs: dict[tuple[str, str], CallableSpec] = {
        (s.department_id, s.need_id): _hydrate_spec(s) for s in spec_rows
    }
    return Dispatcher(connectors=prepared, callable_specs=specs)
