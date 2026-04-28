"""Connector orchestration: create + validate, list, delete, retest.

Pure orchestration over the new openlia.connectors core + the Connector ORM.
No FastAPI imports here; routes call into this module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from openlia.connectors.builtins import get_builtin
from openlia.connectors.mcp_transport import default_session_factory
from openlia.connectors.types import (
    Category,
    ConnectorSource,
    ConnectorStatus,
    MCPLaunchSpec,
)
from openlia.connectors.validate import (
    ValidationFailure,
    ValidationOk,
    validate_connector,
)
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector


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


# NOTE: scope_connectors and compute_readiness were removed with the
# tool_allowlists table. Phase 7 (built-in template registry) and Phase 10
# (department health) reintroduce equivalent flows over runner_callable_specs.
