"""Connector orchestration: create + validate, list, delete, retest.

Pure orchestration over the new openlia.connectors core + the Connector ORM.
No FastAPI imports here; routes call into this module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from openlia.connectors.builtins import get_builtin
from openlia.connectors.mcp_transport import default_session_factory
from openlia.connectors.scope import (
    DepartmentRequirements,
    ScopeLLMClient,
    scope_connector,
)
from openlia.connectors.types import (
    Category,
    ConnectorSource,
    ConnectorStatus,
    MCPLaunchSpec,
    ScopedBy,
    ToolDefinition,
)
from openlia.connectors.validate import (
    ValidationFailure,
    ValidationOk,
    validate_connector,
)
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector, ToolAllowlist


def _resolve_launch_for_validation(spec: MCPLaunchSpec) -> tuple[MCPLaunchSpec, str | None]:
    """BUILT_IN spec -> CLI launch resolved from the template, plus its canary tool."""

    if spec.kind is ConnectorSource.BUILT_IN:
        tpl = get_builtin(spec.template_id or "")
        return (
            MCPLaunchSpec.cli(argv=list(tpl.cli_argv), env={tpl.api_key_env_var: ""}),
            tpl.canary_tool,
        )
    return spec, None


async def create_connector(
    session: Session,
    *,
    provider_id: str,
    source: ConnectorSource,
    category: Category,
    launch: MCPLaunchSpec,
    credentials_ref: str | None,
) -> Connector:
    cid = str(uuid.uuid4())
    row = Connector(
        id=cid,
        provider_id=provider_id,
        source=source.value,
        category=category.value,
        launch=launch.to_json(),
        credentials_ref=credentials_ref,
        status=ConnectorStatus.PENDING.value,
    )
    session.add(row)
    session.flush()

    resolved_spec, canary = _resolve_launch_for_validation(launch)
    result = await validate_connector(
        spec=resolved_spec,
        canary_tool=canary,
        session_factory=default_session_factory,
    )
    if isinstance(result, ValidationOk):
        row.status = ConnectorStatus.VALIDATED.value
        row.cached_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in result.tools
        ]
        row.last_validated_at = datetime.now(UTC)
        row.last_error = None
    else:
        assert isinstance(result, ValidationFailure)
        row.status = ConnectorStatus.FAILED.value
        row.last_error = result.error

    session.commit()
    session.refresh(row)
    return row


def list_connectors(session: Session) -> list[Connector]:
    return list(session.query(Connector).order_by(Connector.created_at).all())


def delete_connector(session: Session, connector_id: str) -> None:
    row = session.get(Connector, connector_id)
    if row is None:
        return
    session.delete(row)
    session.commit()


async def revalidate_connector(session: Session, connector_id: str) -> Connector | None:
    row = session.get(Connector, connector_id)
    if row is None:
        return None
    spec = MCPLaunchSpec.from_json(row.launch)
    resolved_spec, canary = _resolve_launch_for_validation(spec)
    result = await validate_connector(
        spec=resolved_spec,
        canary_tool=canary,
        session_factory=default_session_factory,
    )
    if isinstance(result, ValidationOk):
        row.status = ConnectorStatus.VALIDATED.value
        row.cached_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in result.tools
        ]
        row.last_validated_at = datetime.now(UTC)
        row.last_error = None
    else:
        assert isinstance(result, ValidationFailure)
        row.status = ConnectorStatus.FAILED.value
        row.last_error = result.error
    session.commit()
    session.refresh(row)
    return row


async def scope_connectors(
    session: Session,
    *,
    connector_ids: list[str] | None,
    llm: ScopeLLMClient,
    requirements: dict[str, DepartmentRequirements],
) -> dict[str, int]:
    """Scope each VALIDATED connector to departments.

    BUILT_IN copies the shipped allowlist; user MCP/CLI calls the LLM.
    Returns a dict of connector_id -> rows_written.
    """

    rows = list_connectors(session)
    if connector_ids is not None:
        wanted = set(connector_ids)
        rows = [r for r in rows if r.id in wanted]
    rows = [r for r in rows if r.status == ConnectorStatus.VALIDATED.value]

    counts: dict[str, int] = {}
    for row in rows:
        # Wipe any previous allowlist for this connector first.
        session.query(ToolAllowlist).filter_by(connector_id=row.id).delete()

        if row.source == ConnectorSource.BUILT_IN.value:
            spec = MCPLaunchSpec.from_json(row.launch)
            tpl = get_builtin(spec.template_id or "")
            for a in tpl.shipped_allowlist:
                session.add(
                    ToolAllowlist(
                        id=str(uuid.uuid4()),
                        department_id=a.department_id,
                        connector_id=row.id,
                        tool_name=a.tool_name,
                        scoped_by=ScopedBy.BUILT_IN_MAP.value,
                    )
                )
            counts[row.id] = len(tpl.shipped_allowlist)
        else:
            tools = [
                ToolDefinition(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("input_schema", {}),
                )
                for t in (row.cached_tools or [])
            ]
            scoped = await scope_connector(
                connector_id=row.id,
                provider_id=row.provider_id,
                category=Category(row.category),
                tools=tools,
                requirements=requirements,
                llm=llm,
            )
            for s in scoped:
                session.add(
                    ToolAllowlist(
                        id=str(uuid.uuid4()),
                        department_id=s.department_id,
                        connector_id=row.id,
                        tool_name=s.tool_name,
                        scoped_by=ScopedBy.LLM_ADAPTER.value,
                    )
                )
            counts[row.id] = len(scoped)
    session.commit()
    return counts


def compute_readiness(session: Session) -> list[dict[str, Any]]:
    """Compute per-department readiness from VALIDATED connectors + their allowlist rows.

    See spec §5 Phase 4b. Per-(department, category) status:
      required + >=1 row -> "ok"
      required + 0 rows  -> "missing"
      optional + >=1 row -> "enhanced"
      optional + 0 rows  -> "basic"
    department.ready iff every required category is "ok".
    """

    from openlia.departments import get_all_requirements

    reqs = get_all_requirements()
    conns = {
        r.id: r
        for r in session.query(Connector)
        .filter(Connector.status == ConnectorStatus.VALIDATED.value)
        .all()
    }
    rows = session.query(ToolAllowlist).all()

    out: list[dict[str, Any]] = []
    for dep_id, dep_req in reqs.items():
        cats: list[dict[str, Any]] = []
        ready = True
        for cat_value, body in dep_req.per_category.items():
            relevant = [
                r
                for r in rows
                if r.department_id == dep_id
                and r.connector_id in conns
                and conns[r.connector_id].category == cat_value
            ]
            providers = sorted({conns[r.connector_id].provider_id for r in relevant})
            tool_count = len(relevant)
            required = bool(body["required"])
            if required:
                cat_status = "ok" if tool_count > 0 else "missing"
                if tool_count == 0:
                    ready = False
            else:
                cat_status = "enhanced" if tool_count > 0 else "basic"
            cats.append(
                {
                    "category": cat_value,
                    "required": required,
                    "status": cat_status,
                    "tool_count": tool_count,
                    "providers": providers,
                }
            )
        out.append({"department_id": dep_id, "ready": ready, "categories": cats})
    return out
