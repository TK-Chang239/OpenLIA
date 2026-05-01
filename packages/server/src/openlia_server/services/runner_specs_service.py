"""Wizard-time spec proposal + approval service.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.

After a connector is validated, this service iterates the runner-bearing
departments whose required/optional categories overlap the connector, calls
the wizard-time adapter LLM to propose a `CallableSpec` per `(dept, need)`,
runs a canary, and stashes the drafts in an in-memory cache. The wizard
surfaces the cache via `GET /api/connectors/{id}/proposed-specs` and admins
approve a draft via `POST /api/connectors/{id}/proposed-specs/approve`,
which persists the spec into `runner_callable_specs`.

NOTE (Phase 6 stub): Phase 8 authors `<dept>.needs.yaml` files and adds the
`requires_runner` flag + `required_categories` / `optional_categories` to
each Department class. Until then, the dept-needs / dept-categories lookups
return empty values, so `propose_specs` produces an empty list. The route
still works end-to-end so frontend work in Phase 11 can stub against it.
"""

from __future__ import annotations

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
from openlia_server.services.dispatcher_factory import _prepare_connector

log = logging.getLogger(__name__)


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
# Phase 8 will replace these stubs with real lookups.
# ---------------------------------------------------------------------------

# `dept_id -> [RunnerNeed, ...]`. Phase 8 hydrates this from each department's
# `<dept>.needs.yaml` file; for now the empty default keeps the wizard flow
# working end-to-end with no proposals.
_DEPT_NEEDS: dict[str, list[RunnerNeed]] = {}

# `dept_id -> (required_categories, optional_categories)`. Phase 8 sources
# these from `Department.requires_runner / required_categories / optional_categories`
# class attributes.
_DEPT_CATEGORIES: dict[str, tuple[set[Category], set[Category]]] = {}


def set_dept_needs_for_testing(needs: dict[str, list[RunnerNeed]]) -> None:
    """Test-only helper. Phase 8 replaces with a real loader."""
    _DEPT_NEEDS.clear()
    _DEPT_NEEDS.update(needs)


def set_dept_categories_for_testing(
    categories: dict[str, tuple[set[Category], set[Category]]],
) -> None:
    """Test-only helper. Phase 8 replaces with a real loader."""
    _DEPT_CATEGORIES.clear()
    _DEPT_CATEGORIES.update(categories)


def hydrate_dept_registries() -> None:
    """Populate `_DEPT_NEEDS` / `_DEPT_CATEGORIES` from the live registry.

    Without this, `propose_specs` iterates over empty maps and never
    produces drafts, so every runner-bearing dept stays disabled with
    every need unresolved. Called once at app startup.
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


_PROPOSALS: dict[str, list[ProposedSpec]] = {}
_DEPT_PROPOSALS: dict[str, list[ProposedSpec]] = {}


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
    # Phase 8 populates _DEPT_NEEDS / _DEPT_CATEGORIES; until then this loop
    # is a no-op for shipped builds.
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
            except ResolverError as exc:
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
    return list(proposals)


async def propose_specs_for_department(
    session: Session,
    *,
    department_id: str,
    llm_client: LlmClient,
) -> list[ProposedSpec]:
    """Per-department resolve.

    Iterates every validated connector whose category overlaps the
    department's required ∪ optional categories. For each (department,
    need), tries each in-scope connector in turn and keeps the first
    spec that resolves. If no connector produces a valid spec the proposal
    is marked `unsatisfiable=True`. Results are cached in
    `_DEPT_PROPOSALS[department_id]`.
    """
    needs = _DEPT_NEEDS.get(department_id) or []
    if not needs:
        clear_dept_proposed_specs(department_id)
        return []

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
        chosen: ProposedSpec | None = None
        last_error: str | None = None
        for row in in_scope:
            access_mode, inventory, instance_factory = _select_access_mode_and_inventory(row)
            if access_mode is None:
                continue
            try:
                spec = await resolve_callable_spec(
                    need=need,
                    connector_inventory=inventory,
                    access_mode=access_mode,  # type: ignore[arg-type]
                    instance_factory=instance_factory,
                    llm_client=llm_client,
                )
            except ResolverError as exc:
                last_error = str(exc)
                continue
            prepared = _prepare_connector(row)
            canary: CanaryResult = await run_canary(
                spec=spec,
                transport=prepared.transport,
                sample_args=_sample_args_for(need),
            )
            chosen = ProposedSpec(
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
            break

        if chosen is None:
            proposals.append(
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
                )
            )
        else:
            proposals.append(chosen)

    _DEPT_PROPOSALS[department_id] = proposals
    return list(proposals)


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
        {"value": match.canary_value, "shape_match": match.shape_match} if match.canary_ok else None
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
