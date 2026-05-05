"""Runtime dispatch for the connector subsystem (v2).

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §8.1, §9.

The dispatcher exposes:

- `candidate_tools()` — full validated tool inventory across all configured
  connectors, prefixed by `provider_id__tool` (chat-department runtime router
  picks from this; no per-dept allowlist or category gate).
- `dispatch_tool_use(prefixed_name, arguments)` — routes a `tool_use` event
  back to the correct connector by `provider_id` prefix.
- `in_department(dept_id)` — async context manager establishing the calling
  department for runner needs.
- `fetch_need(need_id, **runtime_args)` — resolves a `(current_dept, need_id)`
  pair to a persisted `CallableSpec` and invokes it.
- `callable_specs_for(dept_id)` — list helper.

This module is pure logic; the registry, callable specs, and live transports
are passed in so the server layer can hydrate them from SQLAlchemy.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from openlia.connectors.transports import CallableTransport
from openlia.connectors.types import (
    ALLOWED_RESULT_REDUCERS,
    ALLOWED_TRANSFORMS,
    RESULT_REDUCERS,
    TRANSFORMS,
    CallableDefinition,
    CallableSpec,
    Category,
    ConnectorStatus,
    ToolDefinition,
)

PREFIX_SEP = "__"

_current_dept: ContextVar[str | None] = ContextVar("_current_dept", default=None)


class DispatchError(RuntimeError):
    pass


class MissingRequiredArgumentError(DispatchError):
    """Raised by `dispatch_tool_use` when a tool's argument constraints
    fail before the transport is touched. Used to express "exactly one
    of these args is required" — a constraint Anthropic's tool input
    schema validator can't represent (no JSON-Schema combinators).

    `missing` is a tuple of equally-acceptable parameter names; the
    caller should report this in a structured payload so the model
    can recover by retrying with one of them set.
    """

    def __init__(self, tool_name: str, missing: tuple[str, ...]) -> None:
        self.tool_name = tool_name
        self.missing = missing
        joined = " or ".join(f"`{m}`" for m in missing)
        super().__init__(
            f"{tool_name} requires one of {joined}; none were supplied."
        )


class NeedNotResolved(DispatchError):
    pass


class FieldMapError(DispatchError):
    """Raised when a CallableSpec.field_map fails to resolve at runtime.

    Surfaced for: missing source key on an item, missing nested-path
    component, or attempting to walk a non-mapping. The smoke pipeline
    classifies this as ``schema_miss`` and surfaces the offending key.
    """

    pass


def _is_supplied(value: Any) -> bool:
    """Treat None / "" / [] / {} as missing for argument-constraint checks."""
    if value is None:
        return False
    if isinstance(value, str | list | tuple | dict | set | frozenset):
        return len(value) > 0
    return True


def _walk_result_path(value: Any, path: tuple[str, ...], *, need_id: str) -> Any:
    """Reduce a tool result to a nested field per `path`. Empty path returns value unchanged.

    Walks dict keys first, then falls back to attribute access so python_lib
    transports returning Pydantic models / dataclasses traverse cleanly.
    """
    for key in path:
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif hasattr(value, key):
            value = getattr(value, key)
        else:
            raise DispatchError(f"result_path {path!r} missing key {key!r} for need {need_id!r}")
    return value


def _apply_field_map(value: Any, spec: CallableSpec) -> Any:
    """Per-item rename for ``list[dict]``-shape specs (Phase 3).

    No-op for any other shape, ``None``, or ``{}``. Missing source keys or
    non-mapping items raise ``FieldMapError``.
    """
    if spec.shape != "list[dict]" or not spec.field_map:
        return value

    if not isinstance(value, list):
        raise FieldMapError(
            f"spec for need {spec.need_id!r} has shape 'list[dict]' but post-result_path "
            f"value is not a list: got {type(value).__name__}"
        )

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise FieldMapError(
                f"spec for need {spec.need_id!r}: item at index {idx} is not a mapping"
            )
        renamed: dict[str, Any] = {}
        for canonical_key, source in spec.field_map.items():
            source_path: tuple[str, ...] = source if isinstance(source, tuple) else (source,)
            try:
                renamed[canonical_key] = _walk_result_path(item, source_path, need_id=spec.need_id)
            except DispatchError as exc:
                raise FieldMapError(
                    f"spec for need {spec.need_id!r}: field_map[{canonical_key!r}] "
                    f"source {source!r} missing on item at index {idx}"
                ) from exc
        out.append(renamed)
    return out


@dataclass(frozen=True)
class PreparedConnector:
    connector_id: str
    provider_id: str
    category: Category
    status: ConnectorStatus
    transport: CallableTransport
    tools: dict[str, ToolDefinition] = field(default_factory=dict)
    """MCP-shaped tool definitions keyed by unprefixed tool_name. Empty for
    python_lib-only connectors."""
    callables: dict[str, CallableDefinition] = field(default_factory=dict)
    """python_lib introspection keyed by qualname. Empty for MCP-only."""


@dataclass
class Dispatcher:
    connectors: dict[str, PreparedConnector]
    """Keyed by connector_id."""
    callable_specs: dict[tuple[str, str], CallableSpec] = field(default_factory=dict)
    """Keyed by (department_id, need_id)."""
    spec_connector_ids: dict[tuple[str, str], str] = field(default_factory=dict)
    """Authoritative connector ownership per spec, set by the server's
    hydrator from RunnerCallableSpec.connector_id. When present,
    `_connector_for_spec` uses it directly instead of scanning by
    tool/method qualname — required when a spec's method name doesn't
    appear in the connector's introspected callables registry (e.g.
    Firecrawl SDK attaches methods per-instance, so class-walk
    introspection misses them)."""
    chat_connector_blocklist: frozenset[str] = field(default_factory=frozenset)
    """Per-session opt-out: connector_ids in this set are omitted from
    `candidate_tools()` (chat-routing surface) but remain available to
    `fetch_need` so deterministic dept runs are unaffected. Backs the
    chat-input "Tools" dropdown."""
    tool_argument_constraints: dict[str, tuple[tuple[str, str, tuple[tuple[str, ...], ...]], ...]] = field(  # noqa: E501
        default_factory=dict
    )
    """Per-provider pre-dispatch argument constraints. Keyed by
    `provider_id`, each entry is a tuple of
    `(tool_name, kind, payload)` triples. Today only `kind="require_one_of"`
    is supported; `payload` is a tuple of parameter-name groups, one of
    which must be non-empty in the call's `arguments`. Surfaced from
    BuiltInTemplate.tool_argument_constraints by `dispatcher_factory`."""

    # ----- chat candidate pool / tool routing (§8) -----

    def candidate_tools(self) -> list[dict[str, Any]]:
        """Full validated tool inventory across all connectors. Per spec §8.1.

        Connectors in `chat_connector_blocklist` are excluded so a user
        who toggles them off in the chat input never sees their tools
        in the routed pool.
        """
        out: list[dict[str, Any]] = []
        for conn in self.connectors.values():
            if conn.status != ConnectorStatus.VALIDATED:
                continue
            if conn.connector_id in self.chat_connector_blocklist:
                continue
            for tool_name, td in conn.tools.items():
                out.append(
                    {
                        "name": f"{conn.provider_id}{PREFIX_SEP}{tool_name}",
                        "description": td.description,
                        "input_schema": td.input_schema,
                    }
                )
        return out

    async def dispatch_tool_use(self, prefixed_name: str, arguments: dict[str, Any]) -> Any:
        if PREFIX_SEP not in prefixed_name:
            raise DispatchError(f"missing prefix in {prefixed_name!r}")
        provider_id, _, raw_name = prefixed_name.partition(PREFIX_SEP)
        self._enforce_argument_constraints(provider_id, prefixed_name, raw_name, arguments)
        for conn in self.connectors.values():
            if conn.provider_id == provider_id and raw_name in conn.tools:
                return await conn.transport.call_tool(raw_name, arguments)
        raise DispatchError(f"no connector for {prefixed_name!r}")

    def _enforce_argument_constraints(
        self,
        provider_id: str,
        prefixed_name: str,
        raw_name: str,
        arguments: dict[str, Any],
    ) -> None:
        for tool_name, kind, payload in self.tool_argument_constraints.get(provider_id, ()):
            if tool_name != raw_name:
                continue
            if kind != "require_one_of":
                continue
            for group in payload:
                if not any(_is_supplied(arguments.get(p)) for p in group):
                    raise MissingRequiredArgumentError(prefixed_name, group)

    # ----- runner need fetch (§9) -----

    @asynccontextmanager
    async def in_department(self, department_id: str) -> AsyncIterator[None]:
        token = _current_dept.set(department_id)
        try:
            yield
        finally:
            _current_dept.reset(token)

    async def fetch_need(self, need_id: str, **runtime_args: Any) -> Any:
        dept = _current_dept.get()
        if dept is None:
            raise DispatchError(
                "fetch_need requires an active dispatcher.in_department(...) context"
            )
        spec = self.callable_specs.get((dept, need_id))
        if spec is None:
            raise NeedNotResolved(f"no resolved callable spec for ({dept!r}, {need_id!r})")
        conn = self._connector_for_spec(dept, need_id, spec)
        return await self._invoke_spec(conn, spec, runtime_args)

    def callable_specs_for(self, department_id: str) -> list[CallableSpec]:
        return [spec for (d, _), spec in self.callable_specs.items() if d == department_id]

    # ----- private helpers -----

    def _connector_for_spec(self, dept: str, need_id: str, spec: CallableSpec) -> PreparedConnector:
        """Locate the connector that owns this spec.

        Prefers the persisted `spec_connector_ids` map (RunnerCallableSpec.connector_id
        from the DB row). Falls back to scanning by `tool_name`/`method`
        presence so older specs persisted before connector_id was tracked
        keep working.
        """
        cid = self.spec_connector_ids.get((dept, need_id))
        if cid is not None:
            conn = self.connectors.get(cid)
            if conn is not None:
                return conn

        access_mode = spec.access_mode
        if access_mode in {"cli_mcp", "remote_mcp"}:
            tool_name = spec.tool_name
            if tool_name is None:
                raise DispatchError(f"spec for ({dept!r}, {need_id!r}) is MCP but has no tool_name")
            for conn in self.connectors.values():
                if tool_name in conn.tools:
                    return conn
            raise DispatchError(
                f"no connector exposes MCP tool {tool_name!r} for ({dept!r}, {need_id!r})"
            )
        if access_mode == "python_lib":
            method = spec.method
            if method is None:
                raise DispatchError(
                    f"spec for ({dept!r}, {need_id!r}) is python_lib but has no method"
                )
            # Prefer connectors whose `callables` registry knows the method;
            # fall back to any connector matching the spec's module.
            for conn in self.connectors.values():
                if method in conn.callables or any(
                    cd.qualname.endswith(f".{method}") or cd.qualname == method
                    for cd in conn.callables.values()
                ):
                    return conn
            # Last resort: take the first connector whose source declares
            # python_lib so the transport can still attempt the call.
            for conn in self.connectors.values():
                if conn.callables:
                    return conn
            raise DispatchError(f"no python_lib connector available for ({dept!r}, {need_id!r})")
        raise DispatchError(f"unknown access_mode {access_mode!r}")

    async def _invoke_spec(
        self,
        conn: PreparedConnector,
        spec: CallableSpec,
        runtime_args: dict[str, Any],
    ) -> Any:
        """Walk a CallableSpec: apply param_bindings + constants, dispatch."""
        bound: dict[str, Any] = {}

        # Apply param_bindings: rename caller's kwarg -> underlying arg, and
        # apply named transform when present. Runtime args without a
        # matching binding are dropped silently — the dispatcher's contract
        # is that param_bindings + constants together fully describe the
        # call's argument shape. (Earlier behavior passed unbound args
        # through, but that breaks specs that share a need-id with a
        # different shape — e.g. Firecrawl-scrape specs receiving a stray
        # country=US from parse_mr_requirement.)
        for caller_name, value in runtime_args.items():
            binding = spec.param_bindings.get(caller_name)
            if binding is None:
                continue
            if binding.transform is not None:
                if binding.transform not in ALLOWED_TRANSFORMS:
                    raise DispatchError(
                        f"unknown transform {binding.transform!r} in spec for need {spec.need_id!r}"
                    )
                value = TRANSFORMS[binding.transform](value)
            bound[binding.to_arg] = value

        # Merge constants. Constants override caller-supplied values for the
        # same target arg name (per spec §6.4 they are the spec author's intent).
        for k, v in spec.constants.items():
            bound[k] = v

        # Dispatch.
        if spec.access_mode in ("cli_mcp", "remote_mcp"):
            tool_name = spec.tool_name
            if tool_name is None:
                raise DispatchError(f"spec for need {spec.need_id!r} missing tool_name")
            raw = await conn.transport.call_tool(tool_name, bound)
        elif spec.access_mode == "python_lib":
            method = spec.method
            if method is None:
                raise DispatchError(f"spec for need {spec.need_id!r} missing method")
            # The PythonLibTransport (Phase 5) handles instance instantiation
            # and method dispatch internally; we just hand it the method name
            # and bound kwargs.
            raw = await conn.transport.call_tool(method, bound)
        else:
            raise DispatchError(f"unknown access_mode {spec.access_mode!r}")

        if spec.result_reducer is not None:
            if spec.result_reducer not in ALLOWED_RESULT_REDUCERS:
                raise DispatchError(
                    f"unknown result_reducer {spec.result_reducer!r} "
                    f"in spec for need {spec.need_id!r}",
                )
            try:
                raw = RESULT_REDUCERS[spec.result_reducer](raw)
            except (ValueError, TypeError, KeyError) as exc:
                raise DispatchError(
                    f"result_reducer {spec.result_reducer!r} failed for "
                    f"need {spec.need_id!r}: {exc}",
                ) from exc
        walked = _walk_result_path(raw, spec.result_path, need_id=spec.need_id)
        return _apply_field_map(walked, spec)
