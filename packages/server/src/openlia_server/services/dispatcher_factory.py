"""Build a runtime Dispatcher from DB state.

Reads VALIDATED Connector rows + their cached tool lists + ToolAllowlist
rows and returns a hydrated Dispatcher whose transports use
default_session_factory. Built-in launch specs are resolved to their CLI
form via the same helper used by the validate path.

Decryption of api_key_encrypted into the spawned MCP server's env vars
is wired here (BUILT_IN connectors only — user MCP/CLI connectors carry
their secrets in the launch spec itself).
"""

from __future__ import annotations

from openlia.connectors.builtins import get_builtin
from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.mcp_transport import (
    MCPTransport,
    SessionFactory,
    default_session_factory,
)
from openlia.connectors.types import (
    Category,
    ConnectorSource,
    ConnectorStatus,
    MCPLaunchSpec,
    ToolDefinition,
)
from sqlalchemy.orm import Session

from openlia_server.db.crypto import decrypt_for_row
from openlia_server.db.models.connectors import Connector, ToolAllowlist


def _resolved_launch_with_secret(row: Connector) -> MCPLaunchSpec:
    """Resolve BUILT_IN to CLI form and inject the decrypted API key into env."""

    spec = MCPLaunchSpec.from_json(row.launch)
    if spec.kind is not ConnectorSource.BUILT_IN:
        # User-supplied MCP/CLI specs already carry their own auth in headers/env.
        return spec
    tpl = get_builtin(spec.template_id or "")
    env = {tpl.api_key_env_var: ""}
    if row.api_key_encrypted is not None:
        env[tpl.api_key_env_var] = decrypt_for_row(row.id, row.api_key_encrypted)
    return MCPLaunchSpec.cli(argv=list(tpl.cli_argv), env=env)


def build_dispatcher_for_session(
    session: Session,
    *,
    session_factory: SessionFactory = default_session_factory,
) -> Dispatcher:
    """Build a Dispatcher hydrated from the session's current DB state.

    The `session_factory` argument lets tests inject fakes; production
    leaves it as `default_session_factory`.
    """

    rows = (
        session.query(Connector).filter(Connector.status == ConnectorStatus.VALIDATED.value).all()
    )
    prepared: dict[str, PreparedConnector] = {}
    categories: dict[str, Category] = {}
    for row in rows:
        tools = {
            t["name"]: ToolDefinition(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("input_schema", {}),
            )
            for t in (row.cached_tools or [])
        }
        spec = _resolved_launch_with_secret(row)
        transport = MCPTransport(spec=spec, session_factory=session_factory)
        prepared[row.id] = PreparedConnector(
            connector_id=row.id,
            provider_id=row.provider_id,
            transport=transport,
            tools=tools,
        )
        categories[row.id] = Category(row.category)

    allowlist: dict[str, list[tuple[str, str]]] = {}
    for r in session.query(ToolAllowlist).all():
        allowlist.setdefault(r.department_id, []).append((r.connector_id, r.tool_name))

    return Dispatcher(
        connectors=prepared,
        allowlist=allowlist,
        connector_categories=categories,
    )
