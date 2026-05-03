"""Phase 10: end-to-end save flow + audit log persistence.

Single entry point `save_user_picked_spec` that the resolve endpoint
calls. Steps:

1. Build the resolver's inventory from the connector's cached_tools /
   cached_python_callables.
2. Call `resolve_user_picked_spec` (Phase 5 manual-pick).
3. Persist a `ResolverCallLog` row (success or failure).
4. Run `run_smoke` against a transport built from the connector.
5. Persist a `SmokeCallLog` row.
6. On smoke success — persist or update the live `RunnerCallableSpec`
   row, stamp `last_smoke_at`, and return `SaveFlowSuccess`.
7. On smoke failure — leave any prior live spec intact, return
   `SaveFlowFailure` carrying the typed status for the UI.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from openlia.connectors.adapter import (
    LlmClient,
    ResolverError,
    UnsatisfiableNeed,
    resolve_user_picked_spec,
)
from openlia.connectors.transports import CallableTransport
from openlia.connectors.types import (
    CallableDefinition,
    CallableSpec,
    Category,
    InstanceFactory,
    RunnerNeed,
    ToolDefinition,
)
from openlia.departments.loader import load_needs
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import (
    Connector,
    ResolverCallLog,
    RunnerCallableSpec,
    SmokeCallLog,
)
from openlia_server.services.smoke_service import SmokeResult, run_smoke


@dataclass(frozen=True)
class SaveFlowSuccess:
    spec: RunnerCallableSpec
    warning: str | None


@dataclass(frozen=True)
class SaveFlowFailure:
    failure: SmokeResult
    warning: str | None


SaveFlowResult = SaveFlowSuccess | SaveFlowFailure


def _load_need(department_id: str, need_id: str) -> RunnerNeed:
    needs = load_needs(department_id)
    for n in needs:
        if n.id == need_id:
            return n
    raise KeyError(f"need {need_id!r} not declared in {department_id!r} needs.yaml")


def _inventory_from_connector(
    connector: Connector,
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"],
) -> tuple[list[CallableDefinition] | list[ToolDefinition], InstanceFactory | None]:
    if access_mode in ("cli_mcp", "remote_mcp"):
        tools_raw = connector.cached_tools or []
        tools = [
            ToolDefinition(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("input_schema", {}),
            )
            for t in tools_raw
        ]
        return tools, None
    callables_raw = connector.cached_python_callables or []
    callables = [
        CallableDefinition(
            qualname=c["qualname"],
            signature=c.get("signature", "(self) -> None"),
            doc=c.get("doc", ""),
        )
        for c in callables_raw
    ]
    factory: InstanceFactory | None = None
    launch = connector.launch or {}
    for mode in launch.get("modes", []) or []:
        if mode.get("kind") == "python_lib":
            inst = mode.get("instance_factory") or {}
            if inst.get("cls"):
                factory = InstanceFactory(
                    cls=str(inst["cls"]),
                    args=inst.get("args", {}),
                )
            break
    return callables, factory


def _spec_to_dict(spec: CallableSpec) -> dict[str, Any]:
    return {
        "need_id": spec.need_id,
        "access_mode": spec.access_mode,
        "tool_name": spec.tool_name,
        "method": spec.method,
        "module": spec.module,
        "param_bindings": {
            k: {"to_arg": b.to_arg, "transform": b.transform}
            for k, b in spec.param_bindings.items()
        },
        "constants": spec.constants,
        "shape": spec.shape,
        "result_path": list(spec.result_path) if spec.result_path else [],
        "result_reducer": spec.result_reducer,
        "field_map": (
            None
            if spec.field_map is None
            else {k: list(v) if isinstance(v, tuple) else v for k, v in spec.field_map.items()}
        ),
    }


async def save_user_picked_spec(
    *,
    session: Session,
    connector: Connector,
    department_id: str,
    need_id: str,
    resolution_mode: Literal["manual_endpoint", "websearch"],
    user_picked_endpoint: str,
    user_hint: str | None,
    websearch_url: str | None,
    manually_overridden: bool,
    llm_client: LlmClient,
    transport_factory: Callable[[Connector], CallableTransport],
) -> SaveFlowResult:
    need = _load_need(department_id, need_id)

    # Pick an access mode from the connector's launch modes. Prefer
    # remote_mcp / cli_mcp when cached_tools is populated; fall back to
    # python_lib otherwise.
    if connector.cached_tools:
        access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"] = "remote_mcp"
    elif connector.cached_python_callables:
        access_mode = "python_lib"
    else:
        # Empty inventory — let resolver raise.
        access_mode = "remote_mcp"

    inventory, instance_factory = _inventory_from_connector(connector, access_mode)
    category = Category(connector.category)

    # Use the existing spec_id when re-resolving for the same (dept, need)
    # so audit history threads through the same row. For first-time
    # resolves no row exists yet — write logs with `spec_id=None` and
    # patch them to the freshly-created spec_id on commit.
    existing_spec_id = _existing_spec_id(session, department_id=department_id, need_id=need_id)
    log_spec_id: str | None = existing_spec_id
    spec_id = existing_spec_id or str(uuid4())
    log_request = {
        "user_picked_endpoint": user_picked_endpoint,
        "user_hint": user_hint,
        "websearch_url": websearch_url,
        "resolution_mode": resolution_mode,
        "connector_id": connector.id,
    }

    try:
        result = await resolve_user_picked_spec(
            need=need,
            connector_inventory=inventory,
            access_mode=access_mode,
            connector_category=category,
            instance_factory=instance_factory,
            llm_client=llm_client,
            user_picked_endpoint=user_picked_endpoint,
            user_hint=user_hint,
            websearch_url=websearch_url,
        )
    except (ResolverError, UnsatisfiableNeed, ValueError) as exc:
        session.add(
            ResolverCallLog(
                id=str(uuid4()),
                spec_id=log_spec_id,
                department_id=department_id,
                need_id=need_id,
                request=log_request,
                response=None,
                status="invalid_output",
                error_class=type(exc).__name__,
                error_message=str(exc),
            )
        )
        session.commit()
        # Surface as a synthetic schema_miss so the UI's failure panel
        # can render a uniform recovery affordance.
        return SaveFlowFailure(
            failure=SmokeResult(
                status="schema_miss",
                attempts=0,
                error_class=type(exc).__name__,
                error_message=str(exc),
                response_excerpt=None,
            ),
            warning=None,
        )

    session.add(
        ResolverCallLog(
            id=str(uuid4()),
            spec_id=log_spec_id,
            department_id=department_id,
            need_id=need_id,
            request=log_request,
            response=_spec_to_dict(result.spec),
            status="success",
            error_class=None,
            error_message=None,
        )
    )
    session.commit()

    # Run smoke through a transport that the caller built from the connector.
    transport = transport_factory(connector)
    try:
        smoke = await run_smoke(spec=result.spec, transport=transport)
    finally:
        try:
            await transport.aclose()
        except Exception:
            pass

    session.add(
        SmokeCallLog(
            id=str(uuid4()),
            spec_id=log_spec_id,
            args={
                "endpoint": user_picked_endpoint,
                "constants": result.spec.constants,
            },
            status=smoke.status,
            attempt=smoke.attempts,
            error_class=smoke.error_class,
            error_message=smoke.error_message,
            response_excerpt=smoke.response_excerpt,
        )
    )

    if smoke.status != "success":
        session.commit()
        return SaveFlowFailure(failure=smoke, warning=result.warning)

    # Persist or update the live RunnerCallableSpec row.
    row = (
        session.query(RunnerCallableSpec)
        .filter(
            RunnerCallableSpec.department_id == department_id,
            RunnerCallableSpec.need_id == need_id,
        )
        .one_or_none()
    )
    spec_dict = _spec_to_dict(result.spec)
    now = datetime.now(UTC)
    if row is None:
        row = RunnerCallableSpec(
            id=spec_id,
            department_id=department_id,
            need_id=need_id,
            connector_id=connector.id,
            access_mode=access_mode,
            spec=spec_dict,
            resolution_mode=resolution_mode,
            user_inputs={
                "user_picked_endpoint": user_picked_endpoint,
                "user_hint": user_hint,
                "websearch_url": websearch_url,
            },
            llm_warning=result.warning,
            manually_overridden=manually_overridden,
            last_smoke_at=now,
        )
        session.add(row)
    else:
        row.connector_id = connector.id
        row.access_mode = access_mode
        row.spec = spec_dict
        row.resolution_mode = resolution_mode
        row.user_inputs = {
            "user_picked_endpoint": user_picked_endpoint,
            "user_hint": user_hint,
            "websearch_url": websearch_url,
        }
        row.llm_warning = result.warning
        row.manually_overridden = manually_overridden
        row.last_smoke_at = now
    session.flush()
    # First-time resolves wrote audit rows with `spec_id=None`; backfill
    # to point at the freshly-created spec.
    if log_spec_id is None:
        from sqlalchemy import update

        session.execute(
            update(ResolverCallLog)
            .where(ResolverCallLog.spec_id.is_(None))
            .where(ResolverCallLog.department_id == department_id)
            .where(ResolverCallLog.need_id == need_id)
            .values(spec_id=row.id)
        )
        session.execute(
            update(SmokeCallLog)
            .where(SmokeCallLog.spec_id.is_(None))
            .where(SmokeCallLog.args["endpoint"].as_string() == user_picked_endpoint)
            .values(spec_id=row.id)
        )
    session.commit()
    return SaveFlowSuccess(spec=row, warning=result.warning)


def _existing_spec_id(session: Session, *, department_id: str, need_id: str) -> str | None:
    row = (
        session.query(RunnerCallableSpec)
        .filter(
            RunnerCallableSpec.department_id == department_id,
            RunnerCallableSpec.need_id == need_id,
        )
        .one_or_none()
    )
    return row.id if row is not None else None


def get_history(session: Session, *, spec_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent ResolverCallLog + SmokeCallLog rows for `spec_id`."""
    out: list[dict[str, Any]] = []
    resolver_rows = (
        session.query(ResolverCallLog)
        .filter(ResolverCallLog.spec_id == spec_id)
        .order_by(ResolverCallLog.created_at.desc())
        .limit(limit)
        .all()
    )
    for r in resolver_rows:
        out.append(
            {
                "kind": "resolver",
                "status": r.status,
                "error_class": r.error_class,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    smoke_rows = (
        session.query(SmokeCallLog)
        .filter(SmokeCallLog.spec_id == spec_id)
        .order_by(SmokeCallLog.created_at.desc())
        .limit(limit)
        .all()
    )
    for s in smoke_rows:
        out.append(
            {
                "kind": "smoke",
                "status": s.status,
                "error_class": s.error_class,
                "error_message": s.error_message,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "attempt": s.attempt,
            }
        )
    out.sort(key=lambda e: e["created_at"] or "", reverse=True)
    return out


__all__ = [
    "SaveFlowFailure",
    "SaveFlowResult",
    "SaveFlowSuccess",
    "get_history",
    "save_user_picked_spec",
]
