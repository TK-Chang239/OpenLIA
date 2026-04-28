"""Connector orchestration: create + validate, list, delete, retest (v2).

Pure orchestration over the v2 connector core (LaunchSpec, transports) +
the Connector ORM. No FastAPI imports here; routes call into this module.

Validation flow (per spec §5):
  1. Persist the connector row in PENDING.
  2. For each declared mode in `launch.modes`, build a transport and call
     `list_tools()`. The first mode whose `list_tools()` succeeds populates
     `cached_tools`; on python_lib we additionally introspect the module
     and populate `cached_python_callables`.
  3. Mark VALIDATED on success, FAILED on the first persistent error.

Department-health invalidation (Phase 10): every mutation that can
flip a dept from active to disabled or back invokes
`dept_health.recompute(...)` so route handlers reading
`app.state.dept_health` see consistent values.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from openlia.connectors.adapter.introspect import introspect_python_lib
from openlia.connectors.transports import CallableTransport
from openlia.connectors.types import (
    Category,
    ConnectorSource,
    ConnectorStatus,
    LaunchSpec,
)
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector
from openlia_server.services.dispatcher_factory import _build_transport, _select_mode

log = logging.getLogger(__name__)


# Optional invalidation hook installed by the FastAPI app at startup. The
# server wires this to `dept_health.recompute(session)` so every mutation
# that can change validated-connector inventory keeps the cached health
# map in sync. The default is a no-op so unit tests that exercise this
# module in isolation don't need to install a callback.
_invalidation_hook: Callable[[Session], None] | None = None


def set_dept_health_hook(hook: Callable[[Session], None] | None) -> None:
    """Install the dept-health recompute callback. Called by app startup."""
    global _invalidation_hook
    _invalidation_hook = hook


def _invalidate(session: Session) -> None:
    if _invalidation_hook is None:
        return
    try:
        _invalidation_hook(session)
    except Exception:
        # Health derivation failures must not mask the underlying mutation.
        log.exception("dept_health recompute failed during connector mutation")


@dataclass(frozen=True)
class ValidationOk:
    tools: list[dict[str, Any]]
    python_callables: list[dict[str, Any]]


@dataclass(frozen=True)
class ValidationFailure:
    error: str


ValidationResult = ValidationOk | ValidationFailure


async def _validate_launch(launch: dict[str, Any], secrets: dict[str, str]) -> ValidationResult:
    """Pick the highest-priority mode and exercise it via `list_tools()`.

    For python_lib we also introspect the module to populate
    `cached_python_callables` so the wizard adapter has a callable
    inventory to bind against.
    """
    selected_mode = _select_mode(launch)
    if selected_mode is None:
        return ValidationFailure(error="launch spec has no recognised modes")

    transport: CallableTransport = _build_transport(
        connector_id="<validating>",
        mode=selected_mode,
        secrets=secrets,
    )
    try:
        try:
            raw_tools = await transport.list_tools()
        except Exception as exc:
            return ValidationFailure(error=f"list_tools failed: {exc}")

        tools: list[dict[str, Any]] = []
        for entry in raw_tools or []:
            if isinstance(entry, dict):
                tools.append(
                    {
                        "name": entry.get("name", ""),
                        "description": entry.get("description", ""),
                        "input_schema": entry.get("input_schema", {}),
                    }
                )
            else:
                tools.append(
                    {
                        "name": getattr(entry, "name", ""),
                        "description": getattr(entry, "description", ""),
                        "input_schema": getattr(entry, "input_schema", {}),
                    }
                )

        python_callables: list[dict[str, Any]] = []
        if selected_mode.get("kind") == "python_lib":
            module_name = selected_mode.get("import_module", "")
            try:
                defs = introspect_python_lib(module_name)
            except Exception as exc:
                return ValidationFailure(error=f"introspect_python_lib failed: {exc}")
            python_callables = [
                {"qualname": d.qualname, "signature": d.signature, "doc": d.doc} for d in defs
            ]

        return ValidationOk(tools=tools, python_callables=python_callables)
    finally:
        try:
            await transport.aclose()
        except Exception:
            pass


def _launch_to_dict(launch: LaunchSpec | dict[str, Any]) -> dict[str, Any]:
    if isinstance(launch, dict):
        return launch
    modes_out: list[dict[str, Any]] = []
    for mode in launch.modes:
        if mode.kind == "cli_mcp":
            modes_out.append(
                {
                    "kind": "cli_mcp",
                    "argv": list(mode.argv),
                    "env_keys": list(mode.env_keys),
                }
            )
        elif mode.kind == "remote_mcp":
            modes_out.append(
                {
                    "kind": "remote_mcp",
                    "url": mode.url,
                    "headers": dict(mode.headers),
                }
            )
        elif mode.kind == "python_lib":
            modes_out.append(
                {
                    "kind": "python_lib",
                    "pip_name": mode.pip_name,
                    "pip_version": mode.pip_version,
                    "import_module": mode.import_module,
                    "instance_factory": {
                        "cls": mode.instance_factory.cls,
                        "args": dict(mode.instance_factory.args),
                    },
                }
            )
    return {"modes": modes_out}


async def create_connector(
    session: Session,
    *,
    provider_id: str,
    display_name: str,
    source: ConnectorSource,
    category: Category,
    launch: LaunchSpec | dict[str, Any],
    secrets: dict[str, str] | None = None,
) -> Connector:
    cid = str(uuid.uuid4())
    launch_json = _launch_to_dict(launch)
    row = Connector(
        id=cid,
        provider_id=provider_id,
        display_name=display_name,
        source=source.value,
        category=category.value,
        launch=launch_json,
        secrets=secrets or {},
        status=ConnectorStatus.PENDING.value,
    )
    session.add(row)
    session.flush()

    result = await _validate_launch(launch_json, secrets or {})
    if isinstance(result, ValidationOk):
        row.status = ConnectorStatus.VALIDATED.value
        row.cached_tools = result.tools
        row.cached_python_callables = result.python_callables
        row.validated_at = datetime.now(UTC)
        row.last_error = None
    else:
        row.status = ConnectorStatus.FAILED.value
        row.last_error = result.error

    session.commit()
    session.refresh(row)
    _invalidate(session)
    return row


def list_connectors(session: Session) -> list[Connector]:
    return list(session.query(Connector).order_by(Connector.created_at).all())


def delete_connector(session: Session, connector_id: str) -> None:
    row = session.get(Connector, connector_id)
    if row is None:
        return
    session.delete(row)
    session.commit()
    _invalidate(session)


async def revalidate_connector(session: Session, connector_id: str) -> Connector | None:
    row = session.get(Connector, connector_id)
    if row is None:
        return None
    result = await _validate_launch(row.launch or {}, row.secrets or {})
    if isinstance(result, ValidationOk):
        row.status = ConnectorStatus.VALIDATED.value
        row.cached_tools = result.tools
        row.cached_python_callables = result.python_callables
        row.validated_at = datetime.now(UTC)
        row.last_error = None
    else:
        row.status = ConnectorStatus.FAILED.value
        row.last_error = result.error
    session.commit()
    session.refresh(row)
    _invalidate(session)
    return row
