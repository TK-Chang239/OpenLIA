"""Build a runtime `Dispatcher` from persisted Connector + RunnerCallableSpec rows.

Reads:
- `connectors` rows -> `PreparedConnector` map (keyed by connector_id).
- `runner_callable_specs` rows -> `(department_id, need_id) -> CallableSpec` map.

Per spec §8.1 the dispatcher exposes the full validated tool inventory; per
§9 it resolves runner needs by id within an `in_department(...)` context.

Phase 5 wires the live `CallableTransport` per the connector's `LaunchSpec`:
the first available mode in priority order (`python_lib` > `cli_mcp` >
`remote_mcp`) is realized as a transport instance. Connectors persisted
with a legacy/empty `launch` JSON fall back to `_UnboundTransport` so the
server still boots while their rows wait for migration.

Secret `{NAME}` placeholders are substituted from the connector's secrets
in remote_mcp URLs/headers and cli_mcp argv tokens before transport
construction, so raw keys never need to live in the persisted launch JSON.
"""

from __future__ import annotations

import re
from typing import Any

from openlia.connectors.builtins._registry import get_template
from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.transports import CallableTransport
from openlia.connectors.transports.mcp_cli import CliMcpTransport
from openlia.connectors.transports.mcp_remote import RemoteMcpTransport
from openlia.connectors.transports.python_lib import PythonLibTransport
from openlia.connectors.types import (
    CallableDefinition,
    CallableSpec,
    Category,
    CliMcpMode,
    ConnectorStatus,
    InstanceFactory,
    ParamBinding,
    RemoteMcpMode,
    ToolDefinition,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector, RunnerCallableSpec

_MODE_PRIORITY = ("python_lib", "cli_mcp", "remote_mcp")

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _substitute_secrets(value: str, secrets: dict[str, str]) -> str:
    """Replace every `{NAME}` token in `value` with `secrets[NAME]`.
    Tokens without a matching secret are left literal so a missing key
    surfaces as an obvious failure (e.g. 401) rather than silently
    coercing to an empty string.
    """
    return _PLACEHOLDER_RE.sub(lambda m: secrets.get(m.group(1), m.group(0)), value)


class _UnboundTransport:
    """Fallback transport for legacy connector rows.

    Used when `Connector.launch` is empty or doesn't match the v2
    `{"modes": [...]}` shape — i.e. rows persisted before the launch-spec
    migration. Any invocation fails loudly; `candidate_tools()` still works
    because it never touches the transport.
    """

    def __init__(self, connector_id: str) -> None:
        self._connector_id = connector_id

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise RuntimeError(
            f"connector {self._connector_id!r} has no live transport: "
            "launch spec is empty or pre-v2 (legacy row)"
        )

    async def list_tools(self) -> list[dict]:
        return []

    async def aclose(self) -> None:
        return None


def _select_mode(launch: dict | None) -> dict | None:
    """Pick the first persisted mode dict matching the priority order.

    Returns `None` for legacy/empty payloads so callers can fall back.
    """
    if not isinstance(launch, dict):
        return None
    modes = launch.get("modes")
    if not isinstance(modes, list) or not modes:
        return None
    by_kind = {m.get("kind"): m for m in modes if isinstance(m, dict)}
    for kind in _MODE_PRIORITY:
        if kind in by_kind:
            return by_kind[kind]
    return None


def _build_transport(connector_id: str, mode: dict, secrets: dict[str, str]) -> CallableTransport:
    kind = mode.get("kind")
    if kind == "python_lib":
        factory_raw = mode.get("instance_factory") or {}
        instance_factory = InstanceFactory(
            cls=factory_raw["cls"],
            args=dict(factory_raw.get("args") or {}),
        )
        return PythonLibTransport(
            module=mode["import_module"],
            instance_factory=instance_factory,
            secrets=secrets,
        )
    if kind == "cli_mcp":
        # Substitute `{NAME}` placeholders in argv tokens from secrets, mirroring
        # the remote_mcp URL/header substitution below. This lets an API key be
        # supplied as a positional CLI arg (e.g. `uvx marketdata-mcp-server {KEY}`)
        # without persisting the raw key in launch JSON. Unmatched placeholders
        # stay literal so a missing secret surfaces as an obvious failure.
        argv = [
            _substitute_secrets(tok, secrets) if isinstance(tok, str) else tok
            for tok in (mode.get("argv") or [])
        ]
        cli_mode = CliMcpMode(
            kind="cli_mcp",
            argv=argv,
            env_keys=list(mode.get("env_keys") or []),
        )
        return CliMcpTransport(mode=cli_mode, secrets=secrets)
    if kind == "remote_mcp":
        # Built-in templates declare URLs and headers with `{ENV_VAR_NAME}`
        # placeholders that must be substituted with values from `secrets`
        # before the request hits the upstream server. Without this, FMP
        # (`?apikey={FMP_API_KEY}`) and Firecrawl
        # (`mcp.firecrawl.dev/{FIRECRAWL_API_KEY}/v2/mcp`) pass the literal
        # placeholder and validation passes silently while runtime calls
        # 401 out.
        url = _substitute_secrets(mode["url"], secrets)
        headers = {
            k: _substitute_secrets(v, secrets) if isinstance(v, str) else v
            for k, v in (mode.get("headers") or {}).items()
        }
        remote_mode = RemoteMcpMode(kind="remote_mcp", url=url, headers=headers)
        return RemoteMcpTransport(mode=remote_mode)
    # Unknown kind: surface as an _UnboundTransport rather than crashing boot.
    return _UnboundTransport(connector_id)


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

    secrets: dict[str, str] = dict(row.secrets or {})
    selected_mode = _select_mode(row.launch)
    transport: CallableTransport
    if selected_mode is None:
        # Backward compatibility: legacy rows without a v2 `modes` array.
        transport = _UnboundTransport(row.id)
    else:
        transport = _build_transport(row.id, selected_mode, secrets)

    return PreparedConnector(
        connector_id=row.id,
        provider_id=row.provider_id,
        category=Category(row.category),
        status=ConnectorStatus(row.status),
        transport=transport,
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
        result_path=tuple(raw.get("result_path") or ()),
        result_reducer=raw.get("result_reducer"),
        field_map=raw.get("field_map") or None,
    )


def build_dispatcher(
    session: Session,
    *,
    disabled_connector_ids: tuple[str, ...] | frozenset[str] = (),
) -> Dispatcher:
    """Build a runtime `Dispatcher` from persisted connectors and specs.

    `disabled_connector_ids` is a per-session opt-out: any connector whose
    `id` is in this set is omitted from `candidate_tools()` so the chat
    runtime router never sees it and the model can never call it. The
    connector still lives in `dispatcher.connectors` so deterministic
    dept runs (`fetch_need`) bound to that connector keep working — only
    the chat-routing surface narrows.
    """
    disabled = frozenset(disabled_connector_ids)
    connector_rows = session.execute(select(Connector)).scalars().all()
    spec_rows = session.execute(select(RunnerCallableSpec)).scalars().all()

    prepared = {row.id: _prepare_connector(row) for row in connector_rows}
    specs: dict[tuple[str, str], CallableSpec] = {
        (s.department_id, s.need_id): _hydrate_spec(s) for s in spec_rows
    }
    spec_connector_ids: dict[tuple[str, str], str] = {
        (s.department_id, s.need_id): s.connector_id for s in spec_rows
    }
    # Surface each built-in template's `tool_argument_constraints` so the
    # dispatcher can short-circuit known-bad calls before the SDK round-trip
    # (e.g. EODHD's `financial_news` requires `s` OR `t` per upstream API).
    constraints: dict[str, tuple[tuple[str, str, tuple[tuple[str, ...], ...]], ...]] = {}
    for prep in prepared.values():
        template = get_template(prep.provider_id)
        if template is None:
            continue
        if template.tool_argument_constraints:
            constraints[prep.provider_id] = tuple(template.tool_argument_constraints)
    return Dispatcher(
        connectors=prepared,
        callable_specs=specs,
        spec_connector_ids=spec_connector_ids,
        chat_connector_blocklist=disabled,
        tool_argument_constraints=constraints,
    )
