"""Wizard-time spec proposal + approval service.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.
Plan: docs/superpowers/plans/2026-04-30-adapter-resolver-grounding.md.

Two coexisting flows:

1. **Per-department resolve (current).** `propose_specs_for_department`
   aggregates the inventory across every validated connector whose category
   overlaps the department's required-or-optional categories, hands each one
   to the agentic resolver client, and emits one proposal per (dept, need)
   tagged with the chosen `connector_id` (or `unsatisfiable=True`).
   `propose_spec_for_need` re-resolves a single row in place, optionally
   excluding connectors the user has rejected. Approvals persist via
   `approve_dept_spec`.

2. **Per-connector resolve (legacy).** `propose_specs(connector_id=...)`
   plus `approve_spec` remain wired for the older inline review on the
   Connectors step and the admin Re-resolve button. Both write to
   `runner_callable_specs` via the same `(department_id, need_id)`
   uniqueness contract, so either flow can be used to land a row.

A live tool-call event log (`_RESOLVE_EVENTS`) is populated by the agentic
loop while a dept resolve is in flight; the frontend polls
`GET /api/departments/{id}/proposed-specs/events` for the streaming UX.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from openlia.connectors.adapter import (
    CanaryResult,
    LlmClient,
    ResolverError,
    resolve_callable_spec,
    run_canary,
)
from openlia.connectors.types import (
    CallableDefinition,
    CallableSpec,
    Category,
    ConnectorStatus,
    InstanceFactory,
    ParamBinding,
    RunnerNeed,
    ToolDefinition,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector, RunnerCallableSpec
from openlia_server.services.agentic_resolver_client import AgenticResolverError
from openlia_server.services.dispatcher_factory import _prepare_connector

log = logging.getLogger(__name__)


def _jsonify(value: Any) -> Any:
    """Coerce a canary value to a JSON-safe shape before persisting.

    MCP transports return SDK objects (e.g. `CallToolResult`) that are not
    JSON serializable. Round-trip through `json.dumps(default=str)` so any
    non-serializable leaf becomes its `str()` representation, while plain
    dict/list/scalar payloads are unchanged.
    """
    return json.loads(json.dumps(value, default=str))


# Phase 10: dept-health recompute hook. Installed at app startup so every
# spec persistence keeps `app.state.dept_health` in sync with the row state.
_invalidation_hook: Callable[[Session], None] | None = None


def set_dept_health_hook(hook: Callable[[Session], None] | None) -> None:
    """Install the dept-health recompute callback."""
    global _invalidation_hook
    _invalidation_hook = hook


def _invalidate(session: Session) -> None:
    if _invalidation_hook is None:
        return
    try:
        _invalidation_hook(session)
    except Exception:
        log.exception("dept_health recompute failed during runner-spec mutation")


# ---------------------------------------------------------------------------
# Department registries (hydrated at app startup from <dept>.needs.yaml +
# Department class attributes; see hydrate_dept_registries below).
# ---------------------------------------------------------------------------

_DEPT_NEEDS: dict[str, list[RunnerNeed]] = {}
_DEPT_CATEGORIES: dict[str, tuple[set[Category], set[Category]]] = {}


def set_dept_needs_for_testing(needs: dict[str, list[RunnerNeed]]) -> None:
    """Test-only helper to seed `_DEPT_NEEDS` without hitting the registry."""
    _DEPT_NEEDS.clear()
    _DEPT_NEEDS.update(needs)


def set_dept_categories_for_testing(
    categories: dict[str, tuple[set[Category], set[Category]]],
) -> None:
    """Test-only helper to seed `_DEPT_CATEGORIES` without hitting the registry."""
    _DEPT_CATEGORIES.clear()
    _DEPT_CATEGORIES.update(categories)


def hydrate_dept_registries() -> None:
    """Populate `_DEPT_NEEDS` / `_DEPT_CATEGORIES` from the live registry.

    Without this, the resolve services iterate over empty maps and never
    produce drafts, so every runner-bearing dept stays disabled with every
    need unresolved. Called once at app startup.
    """
    from openlia.departments import _REGISTRY
    from openlia.departments.loader import load_needs

    _DEPT_NEEDS.clear()
    _DEPT_CATEGORIES.clear()
    for dept_id, dept in _REGISTRY.items():
        if not getattr(dept, "requires_runner", False):
            continue
        _DEPT_NEEDS[dept_id] = load_needs(dept_id)
        _DEPT_CATEGORIES[dept_id] = (
            set(dept.required_categories),
            set(dept.optional_categories),
        )


# ---------------------------------------------------------------------------
# In-memory proposal cache (per connector_id).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedSpec:
    department_id: str
    need_id: str
    proposed_spec: dict[str, Any]
    canary_value: Any
    canary_ok: bool
    shape_match: bool
    error: str | None
    connector_id: str | None = None
    unsatisfiable: bool = False
    reason: str | None = None


_PROPOSALS: dict[str, list[ProposedSpec]] = {}
_DEPT_PROPOSALS: dict[str, list[ProposedSpec]] = {}

# Per-(department) live event log, populated by the agentic loop while a
# resolve is in flight so the wizard can stream a tool-call log to the
# user. Cleared at the start of each resolve. Capped to keep the list
# bounded under runaway loops.
_RESOLVE_EVENT_LOG_LIMIT = 200
_RESOLVE_EVENTS: dict[str, list[dict[str, Any]]] = {}


def get_resolve_events(department_id: str) -> list[dict[str, Any]]:
    return list(_RESOLVE_EVENTS.get(department_id, []))


def _append_resolve_event(department_id: str, event: dict[str, Any]) -> None:
    log = _RESOLVE_EVENTS.setdefault(department_id, [])
    if len(log) >= _RESOLVE_EVENT_LOG_LIMIT:
        return
    log.append(event)


def _reset_resolve_events(department_id: str) -> None:
    _RESOLVE_EVENTS[department_id] = []


def get_proposed_specs(connector_id: str) -> list[ProposedSpec]:
    return list(_PROPOSALS.get(connector_id, []))


def clear_proposed_specs(connector_id: str) -> None:
    _PROPOSALS.pop(connector_id, None)


def get_dept_proposed_specs(department_id: str) -> list[ProposedSpec]:
    return list(_DEPT_PROPOSALS.get(department_id, []))


def clear_dept_proposed_specs(department_id: str) -> None:
    _DEPT_PROPOSALS.pop(department_id, None)


def list_runner_specs(
    session: Session, *, department_id: str | None = None
) -> list[RunnerCallableSpec]:
    """List persisted `runner_callable_specs`, optionally scoped to a dept."""
    stmt = select(RunnerCallableSpec)
    if department_id is not None:
        stmt = stmt.where(RunnerCallableSpec.department_id == department_id)
    return list(session.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# CallableSpec (de)serialization helpers.
# ---------------------------------------------------------------------------


def _spec_to_dict(spec: CallableSpec) -> dict[str, Any]:
    return {
        "need_id": spec.need_id,
        "access_mode": spec.access_mode,
        "tool_name": spec.tool_name,
        "module": spec.module,
        "instance_factory": (
            {
                "cls": spec.instance_factory.cls,
                "args": dict(spec.instance_factory.args),
            }
            if spec.instance_factory is not None
            else None
        ),
        "method": spec.method,
        "param_bindings": {
            k: {"to_arg": b.to_arg, "transform": b.transform}
            for k, b in spec.param_bindings.items()
        },
        "constants": dict(spec.constants),
        "shape": spec.shape,
    }


def _dict_to_spec(raw: dict[str, Any]) -> CallableSpec:
    bindings: dict[str, ParamBinding] = {}
    for k, b in (raw.get("param_bindings") or {}).items():
        bindings[k] = ParamBinding(to_arg=b["to_arg"], transform=b.get("transform"))
    factory_raw = raw.get("instance_factory")
    instance_factory: InstanceFactory | None = None
    if factory_raw is not None:
        instance_factory = InstanceFactory(
            cls=factory_raw["cls"],
            args=dict(factory_raw.get("args") or {}),
        )
    return CallableSpec(
        need_id=raw["need_id"],
        access_mode=raw["access_mode"],
        tool_name=raw.get("tool_name"),
        module=raw.get("module"),
        instance_factory=instance_factory,
        method=raw.get("method"),
        param_bindings=bindings,
        constants=dict(raw.get("constants") or {}),
        shape=raw.get("shape", "any"),
    )


# ---------------------------------------------------------------------------
# Inventory + access mode resolution.
# ---------------------------------------------------------------------------


_ACCESS_MODE_PRIORITY = ("python_lib", "cli_mcp", "remote_mcp")


def _select_access_mode_and_inventory(
    row: Connector,
) -> tuple[str | None, list[Any], InstanceFactory | None]:
    """Pick a launch mode + matching inventory for adapter resolution.

    Priority matches `dispatcher_factory._MODE_PRIORITY`: python_lib first.
    """
    launch = row.launch or {}
    modes = launch.get("modes") if isinstance(launch, dict) else None
    if not isinstance(modes, list):
        modes = []
    by_kind = {m.get("kind"): m for m in modes if isinstance(m, dict)}
    for kind in _ACCESS_MODE_PRIORITY:
        if kind not in by_kind:
            continue
        if kind == "python_lib":
            inventory: list[Any] = []
            for entry in row.cached_python_callables or []:
                inventory.append(
                    CallableDefinition(
                        qualname=entry["qualname"],
                        signature=entry.get("signature", ""),
                        doc=entry.get("doc", ""),
                    )
                )
            factory_raw = (by_kind[kind] or {}).get("instance_factory") or {}
            instance_factory = InstanceFactory(
                cls=factory_raw.get("cls", ""),
                args=dict(factory_raw.get("args") or {}),
            )
            return kind, inventory, instance_factory
        # MCP modes share the same `cached_tools` inventory.
        inventory = []
        for entry in row.cached_tools or []:
            inventory.append(
                ToolDefinition(
                    name=entry["name"],
                    description=entry.get("description", ""),
                    input_schema=entry.get("input_schema", {}),
                )
            )
        return kind, inventory, None
    return None, [], None


def _sample_args_for(need: RunnerNeed) -> dict[str, Any]:
    """Best-effort placeholder values for canary execution."""
    out: dict[str, Any] = {}
    for p in need.parameters:
        if p.default is not None:
            out[p.name] = p.default
            continue
        t = (p.type or "").lower()
        if "str" in t:
            out[p.name] = "AAPL"
        elif "int" in t:
            out[p.name] = 1
        elif "float" in t:
            out[p.name] = 1.0
        elif "bool" in t:
            out[p.name] = True
        else:
            out[p.name] = ""
    return out


# ---------------------------------------------------------------------------
# Public entry points.
# ---------------------------------------------------------------------------


async def propose_specs(
    session: Session,
    *,
    connector_id: str,
    llm_client: LlmClient,
) -> list[ProposedSpec]:
    """Run the adapter LLM + canary for every (dept, need) overlapping the connector.

    Stashes results in `_PROPOSALS[connector_id]` and returns the list. Drafts
    are NOT persisted here — `approve_spec` writes the chosen ones to the
    `runner_callable_specs` table.
    """
    row = session.get(Connector, connector_id)
    if row is None:
        clear_proposed_specs(connector_id)
        return []
    if row.status != ConnectorStatus.VALIDATED.value:
        clear_proposed_specs(connector_id)
        return []

    access_mode, inventory, instance_factory = _select_access_mode_and_inventory(row)
    if access_mode is None:
        clear_proposed_specs(connector_id)
        return []

    prepared = _prepare_connector(row)
    transport = prepared.transport
    category = Category(row.category)

    proposals: list[ProposedSpec] = []
    for dept_id, needs in _DEPT_NEEDS.items():
        required, optional = _DEPT_CATEGORIES.get(dept_id, (set(), set()))
        if category not in required and category not in optional:
            continue
        for need in needs:
            try:
                spec = await resolve_callable_spec(
                    need=need,
                    connector_inventory=inventory,
                    access_mode=access_mode,  # type: ignore[arg-type]
                    instance_factory=instance_factory,
                    llm_client=llm_client,
                )
            except (ResolverError, AgenticResolverError) as exc:
                proposals.append(
                    ProposedSpec(
                        department_id=dept_id,
                        need_id=need.id,
                        proposed_spec={},
                        canary_value=None,
                        canary_ok=False,
                        shape_match=False,
                        error=str(exc),
                    )
                )
                continue
            canary: CanaryResult = await run_canary(
                spec=spec,
                transport=transport,
                sample_args=_sample_args_for(need),
            )
            proposals.append(
                ProposedSpec(
                    department_id=dept_id,
                    need_id=need.id,
                    proposed_spec=_spec_to_dict(spec),
                    canary_value=canary.value,
                    canary_ok=canary.ok,
                    shape_match=canary.shape_match,
                    error=canary.error,
                )
            )

    _PROPOSALS[connector_id] = proposals
    try:
        await transport.aclose()
    except Exception:
        pass
    return list(proposals)


async def _resolve_one_need(
    *,
    department_id: str,
    need: RunnerNeed,
    in_scope: list[Connector],
    llm_client: LlmClient | None,
    llm_client_factory: Callable[..., LlmClient] | None,
) -> list[ProposedSpec]:
    """Try every in-scope connector and return one candidate per success.

    Earlier behavior stopped at the first connector that resolved. Now we
    collect every connector's spec so the wizard can show alternatives. If
    no connector resolves, returns a single `unsatisfiable=True` placeholder.
    """
    from openlia.connectors.adapter import UnsatisfiableNeed
    from openlia.llm.types import ToolCall

    from openlia_server.services import grounding_service

    candidates: list[ProposedSpec] = []
    last_error: str | None = None
    per_connector_reasons: list[tuple[str, str]] = []
    for row in in_scope:
        access_mode, inventory, instance_factory = _select_access_mode_and_inventory(row)
        if access_mode is None:
            continue
        if llm_client_factory is not None:
            clone_path = grounding_service.path_for(row.id)

            def _listener(
                call: ToolCall,
                _need_id: str = need.id,
                _connector_id: str = row.id,
            ) -> None:
                _append_resolve_event(
                    department_id,
                    {
                        "type": "tool_call",
                        "need_id": _need_id,
                        "connector_id": _connector_id,
                        "name": call.name,
                        "arguments": dict(call.arguments),
                    },
                )

            try:
                client = llm_client_factory(
                    clone_path if clone_path.exists() else None,
                    tool_call_listener=_listener,
                    grounding_paths=row.grounding_paths,
                )
            except TypeError:
                # Older factories (used in tests) — drop optional kwargs.
                client = llm_client_factory(clone_path if clone_path.exists() else None)
        else:
            assert llm_client is not None
            client = llm_client
        try:
            spec = await resolve_callable_spec(
                need=need,
                connector_inventory=inventory,
                access_mode=access_mode,  # type: ignore[arg-type]
                instance_factory=instance_factory,
                llm_client=client,
            )
        except UnsatisfiableNeed as exc:
            last_error = str(exc)
            per_connector_reasons.append((row.id, exc.reason))
            continue
        except (ResolverError, AgenticResolverError) as exc:
            last_error = str(exc)
            per_connector_reasons.append((row.id, str(exc)))
            continue
        prepared = _prepare_connector(row)
        try:
            canary: CanaryResult = await run_canary(
                spec=spec,
                transport=prepared.transport,
                sample_args=_sample_args_for(need),
            )
        finally:
            try:
                await prepared.transport.aclose()
            except Exception:
                pass
        candidates.append(
            ProposedSpec(
                department_id=department_id,
                need_id=need.id,
                proposed_spec=_spec_to_dict(spec),
                canary_value=canary.value,
                canary_ok=canary.ok,
                shape_match=canary.shape_match,
                error=canary.error,
                connector_id=row.id,
                unsatisfiable=False,
            )
        )

    if candidates:
        return candidates
    aggregated_reason = "; ".join(f"{cid[:8]}: {r}" for cid, r in per_connector_reasons) or None
    return [
        ProposedSpec(
            department_id=department_id,
            need_id=need.id,
            proposed_spec={},
            canary_value=None,
            canary_ok=False,
            shape_match=False,
            error=last_error,
            connector_id=None,
            unsatisfiable=True,
            reason=aggregated_reason,
        )
    ]


async def propose_spec_for_need(
    session: Session,
    *,
    department_id: str,
    need_id: str,
    llm_client: LlmClient | None = None,
    llm_client_factory: Callable[..., LlmClient] | None = None,
    exclude_connector_ids: set[str] | None = None,
) -> list[ProposedSpec]:
    """Re-resolve a single (department, need) pair, leaving the rest of the
    cached dept proposals untouched. Returns every candidate produced by
    in-scope connectors (one per connector that resolved).

    `exclude_connector_ids` skips the listed connectors during the in-scope
    sweep — used by the "Try a different connector" button when the auto
    pick was wrong.
    """
    if llm_client is None and llm_client_factory is None:
        raise TypeError("propose_spec_for_need requires llm_client or llm_client_factory")

    needs = _DEPT_NEEDS.get(department_id) or []
    need = next((n for n in needs if n.id == need_id), None)
    if need is None:
        raise KeyError(f"no need {need_id!r} declared for {department_id!r}")

    _reset_resolve_events(department_id)

    required, optional = _DEPT_CATEGORIES.get(department_id, (set(), set()))
    in_scope_categories = required | optional
    rows = list(
        session.execute(
            select(Connector).where(Connector.status == ConnectorStatus.VALIDATED.value)
        )
        .scalars()
        .all()
    )
    in_scope = [r for r in rows if Category(r.category) in in_scope_categories]
    if exclude_connector_ids:
        in_scope = [r for r in in_scope if r.id not in exclude_connector_ids]

    updated = await _resolve_one_need(
        department_id=department_id,
        need=need,
        in_scope=in_scope,
        llm_client=llm_client,
        llm_client_factory=llm_client_factory,
    )

    cached = list(_DEPT_PROPOSALS.get(department_id, []))
    cached = [p for p in cached if p.need_id != need_id]
    cached.extend(updated)
    _DEPT_PROPOSALS[department_id] = cached
    return updated


async def propose_specs_for_department(
    session: Session,
    *,
    department_id: str,
    llm_client: LlmClient | None = None,
    llm_client_factory: Callable[..., LlmClient] | None = None,
) -> list[ProposedSpec]:
    """Per-department resolve.

    Iterates every validated connector whose category overlaps the
    department's required-or-optional categories. For each (department,
    need), tries each in-scope connector in turn and keeps the first
    spec that resolves. If no connector produces a valid spec the proposal
    is marked `unsatisfiable=True`. Results are cached in
    `_DEPT_PROPOSALS[department_id]`.

    Either `llm_client` (legacy: one client for all calls) or
    `llm_client_factory` (preferred: invoked per-connector with that
    connector's grounding clone path, or None) must be supplied. The
    factory variant is what the production agentic resolver uses so the
    LLM gets filesystem tools scoped to the right repo.
    """
    if llm_client is None and llm_client_factory is None:
        raise TypeError("propose_specs_for_department requires llm_client or llm_client_factory")

    needs = _DEPT_NEEDS.get(department_id) or []
    if not needs:
        clear_dept_proposed_specs(department_id)
        return []

    _reset_resolve_events(department_id)

    required, optional = _DEPT_CATEGORIES.get(department_id, (set(), set()))
    in_scope_categories = required | optional

    rows = list(
        session.execute(
            select(Connector).where(Connector.status == ConnectorStatus.VALIDATED.value)
        )
        .scalars()
        .all()
    )
    in_scope = [r for r in rows if Category(r.category) in in_scope_categories]

    proposals: list[ProposedSpec] = []
    for need in needs:
        proposals.extend(
            await _resolve_one_need(
                department_id=department_id,
                need=need,
                in_scope=in_scope,
                llm_client=llm_client,
                llm_client_factory=llm_client_factory,
            )
        )
    _DEPT_PROPOSALS[department_id] = proposals
    return list(proposals)


def approve_dept_spec(
    session: Session,
    *,
    department_id: str,
    need_id: str,
    connector_id: str | None = None,
) -> RunnerCallableSpec:
    """Persist a dept-level proposal to `runner_callable_specs`.

    When the resolver produced multiple candidates for a need, `connector_id`
    selects which one to persist. If omitted and there's only one candidate,
    that candidate is used; if there are multiple and none is specified, the
    first is taken (matches the auto-pick semantics of "Approve all").
    """
    proposals = _DEPT_PROPOSALS.get(department_id, [])
    matches = [p for p in proposals if p.need_id == need_id]
    if not matches:
        raise KeyError(f"no proposed spec for ({department_id!r}, {need_id!r})")
    if connector_id is not None:
        match = next((p for p in matches if p.connector_id == connector_id), None)
        if match is None:
            raise KeyError(
                f"no candidate for ({department_id!r}, {need_id!r}) on connector {connector_id!r}"
            )
    else:
        match = matches[0]
    if match.unsatisfiable or not match.proposed_spec or match.connector_id is None:
        raise ValueError(
            f"proposal for ({department_id!r}, {need_id!r}) is unsatisfiable: "
            f"{match.error or 'no covering connector'}"
        )

    spec = _dict_to_spec(match.proposed_spec)
    existing = session.execute(
        select(RunnerCallableSpec).where(
            RunnerCallableSpec.department_id == department_id,
            RunnerCallableSpec.need_id == need_id,
        )
    ).scalar_one_or_none()

    canary_payload = (
        {"value": _jsonify(match.canary_value), "shape_match": match.shape_match}
        if match.canary_ok
        else None
    )

    if existing is None:
        row = RunnerCallableSpec(
            id=str(uuid.uuid4()),
            department_id=department_id,
            need_id=need_id,
            connector_id=match.connector_id,
            access_mode=spec.access_mode,
            spec=match.proposed_spec,
            canary_value=canary_payload,
        )
        session.add(row)
    else:
        existing.connector_id = match.connector_id
        existing.access_mode = spec.access_mode
        existing.spec = match.proposed_spec
        existing.canary_value = canary_payload
        row = existing

    session.commit()
    session.refresh(row)
    _invalidate(session)
    return row


def approve_spec(
    session: Session,
    *,
    connector_id: str,
    department_id: str,
    need_id: str,
) -> RunnerCallableSpec:
    """Persist a draft proposal to `runner_callable_specs`.

    Replaces any existing row for the `(department_id, need_id)` pair via
    the `uq_dept_need` unique constraint.
    """
    proposals = _PROPOSALS.get(connector_id, [])
    match = next(
        (p for p in proposals if p.department_id == department_id and p.need_id == need_id),
        None,
    )
    if match is None:
        raise KeyError(f"no proposed spec for ({connector_id!r}, {department_id!r}, {need_id!r})")
    if not match.proposed_spec:
        raise ValueError(
            f"proposal for ({department_id!r}, {need_id!r}) failed validation: "
            f"{match.error or 'unknown error'}"
        )

    spec = _dict_to_spec(match.proposed_spec)
    existing = session.execute(
        select(RunnerCallableSpec).where(
            RunnerCallableSpec.department_id == department_id,
            RunnerCallableSpec.need_id == need_id,
        )
    ).scalar_one_or_none()

    canary_payload = (
        {"value": _jsonify(match.canary_value), "shape_match": match.shape_match}
        if match.canary_ok
        else None
    )

    if existing is None:
        row = RunnerCallableSpec(
            id=str(uuid.uuid4()),
            department_id=department_id,
            need_id=need_id,
            connector_id=connector_id,
            access_mode=spec.access_mode,
            spec=match.proposed_spec,
            canary_value=canary_payload,
        )
        session.add(row)
    else:
        existing.connector_id = connector_id
        existing.access_mode = spec.access_mode
        existing.spec = match.proposed_spec
        existing.canary_value = canary_payload
        row = existing

    session.commit()
    session.refresh(row)
    _invalidate(session)
    return row


def proposal_to_dict(p: ProposedSpec) -> dict[str, Any]:
    return asdict(p)
