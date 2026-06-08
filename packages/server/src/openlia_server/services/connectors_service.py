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
import sys
import traceback
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from openlia.connectors.adapter.introspect import introspect_python_lib
from openlia.connectors.builtins._registry import get_template
from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    PythonLibRecipe,
    RemoteMcpRecipe,
)
from openlia.connectors.transports import CallableTransport
from openlia.connectors.types import (
    Category,
    CliMcpMode,
    ConnectorSource,
    ConnectorStatus,
    InstanceFactory,
    LaunchSpec,
    PythonLibMode,
    RemoteMcpMode,
)
from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import Connector, RunnerCallableSpec
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


def _trigger_grounding_clone(session: Session, connector_id: str, *, force: bool = False) -> None:
    """Best-effort: clone the connector's grounding repo on save.

    Failures land on the row as `grounding_status='failed'` (the service
    handles that), so we never raise out of the connector save path.
    """
    try:
        from openlia_server.services import grounding_service

        if force:
            grounding_service.resync_clone(session, connector_id=connector_id)
        else:
            grounding_service.ensure_clone(session, connector_id=connector_id)
    except Exception:
        log.exception("grounding clone trigger failed for connector %s", connector_id)


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


def _format_list_tools_error(mode: dict[str, Any], exc: Exception) -> str:
    """Build an actionable error string for `list_tools()` failures.

    For python_lib mode we want the user to see (a) which Python interpreter
    we tried to import from, (b) the pip package + version they should
    install, and (c) the original exception with traceback. The wizard UI
    truncates long messages and reveals the rest behind a "Show details"
    toggle, so multi-line is fine and desirable here.
    """
    base = f"list_tools failed: {exc}"
    if mode.get("kind") != "python_lib":
        return base
    if not isinstance(exc, ModuleNotFoundError):
        return base

    pip_name = mode.get("pip_name") or mode.get("import_module") or ""
    pip_version = mode.get("pip_version") or ""
    install_target = f"{pip_name}{pip_version}" if pip_name else "<package>"
    import_module = mode.get("import_module", "")
    tb = traceback.format_exception_only(type(exc), exc)
    tb_text = "".join(tb).strip()

    lines = [
        base,
        "",
        f"The python_lib transport could not import '{import_module}'.",
        f"It is not installed in this server's Python environment ({sys.executable}).",
        "",
        "To fix:",
        "  1. Activate the server's Python environment.",
        f"  2. Run:  pip install {install_target}",
        "  3. Restart the server, then click Validate again.",
        "",
        f"Original error: {tb_text}",
    ]
    return "\n".join(lines)


def _overrides_for_provider(provider_id: str) -> dict[str, dict[str, Any]]:
    """Look up `tool_overrides` from a built-in template by provider_id.
    Returns `{}` for non-builtin connectors (custom MCP, etc.)."""
    template = get_template(provider_id)
    if template is None:
        return {}
    return {name: dict(spec) for name, spec in template.tool_overrides}


def _apply_tool_overrides(
    tools: list[dict[str, Any]], overrides: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge per-tool author overrides into the auto-derived tool list.

    Lets a built-in template fix specific tools whose SDK signature is
    looser than the upstream API requires (e.g. EODHD's `financial_news`
    accepts all-None Python kwargs but the API rejects calls without `s`
    or `t`). Override keys replace the corresponding tool field in
    place; unspecified keys pass through unchanged.
    """
    if not overrides:
        return tools
    out: list[dict[str, Any]] = []
    for tool in tools:
        name = tool.get("name", "")
        override = overrides.get(name)
        if override is None:
            out.append(tool)
            continue
        merged = dict(tool)
        merged.update(override)
        out.append(merged)
    return out


async def _validate_launch(
    launch: dict[str, Any],
    secrets: dict[str, str],
    *,
    tool_overrides: dict[str, dict[str, Any]] | None = None,
) -> ValidationResult:
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
            return ValidationFailure(
                error=_format_list_tools_error(selected_mode, exc),
            )

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

        if selected_mode.get("kind") in ("cli_mcp", "remote_mcp") and not tools:
            return ValidationFailure(
                error=(
                    "Connected to the MCP server but it returned no tools. "
                    "The server may be unauthorized (check the API key) or may "
                    "expose nothing usable."
                ),
            )

        python_callables: list[dict[str, Any]] = []
        if selected_mode.get("kind") == "python_lib":
            module_name = selected_mode.get("import_module", "")
            # Filter introspection to the configured instance class so
            # parent SDK classes re-imported into wrapper modules
            # (e.g. xdk.Client inside x_wrapper) don't leak OAuth helpers
            # into the chat-toolbox surface.
            factory = selected_mode.get("instance_factory") or {}
            cls_name = factory.get("cls")
            try:
                defs = introspect_python_lib(module_name, cls_name=cls_name)
            except Exception as exc:
                return ValidationFailure(error=f"introspect_python_lib failed: {exc}")
            python_callables = [
                {"qualname": d.qualname, "signature": d.signature, "doc": d.doc} for d in defs
            ]

        if tool_overrides:
            tools = _apply_tool_overrides(tools, tool_overrides)
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


class DuplicateConnectorError(ValueError):
    """Raised when a connector with the same (provider_id, source) already exists.

    Carries the existing connector's id so callers (route handlers, UIs)
    can render an "already installed" message or offer to update instead.
    """

    def __init__(self, *, provider_id: str, source: str, existing_id: str) -> None:
        super().__init__(
            f"connector already exists for provider={provider_id!r} source={source!r} "
            f"(id={existing_id})"
        )
        self.provider_id = provider_id
        self.source = source
        self.existing_id = existing_id


async def create_connector(
    session: Session,
    *,
    provider_id: str,
    display_name: str,
    source: ConnectorSource,
    category: Category,
    launch: LaunchSpec | dict[str, Any],
    secrets: dict[str, str] | None = None,
    source_repo_url: str | None = None,
    source_repo_revision: str | None = None,
    grounding_paths: list[str] | None = None,
    openapi_url: str | None = None,
) -> Connector:
    existing = (
        session.query(Connector)
        .filter(Connector.provider_id == provider_id, Connector.source == source.value)
        .first()
    )
    if existing is not None:
        raise DuplicateConnectorError(
            provider_id=provider_id, source=source.value, existing_id=existing.id
        )

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
        source_repo_url=source_repo_url,
        source_repo_revision=source_repo_revision,
        grounding_paths=grounding_paths,
        openapi_url=openapi_url,
    )
    session.add(row)
    session.flush()

    result = await _validate_launch(
        launch_json, secrets or {}, tool_overrides=_overrides_for_provider(provider_id)
    )
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
    if row.source_repo_url:
        _trigger_grounding_clone(session, row.id)
    _invalidate(session)
    return row


# Maps each runner need_id to its owning department_id.
# Scoped to Portfolio only — the sole department that uses the
# deterministic-runner chain for live price data.
_NEED_DEPARTMENT_MAP: dict[str, str] = {
    "stock_quote": "portfolio",
    "eod_history": "portfolio",
    "company_profile": "portfolio",
}


def _recipe_to_mode(
    recipe: CliMcpRecipe | RemoteMcpRecipe | PythonLibRecipe,
) -> CliMcpMode | RemoteMcpMode | PythonLibMode:
    if isinstance(recipe, CliMcpRecipe):
        return CliMcpMode(
            kind="cli_mcp",
            argv=list(recipe.argv),
            env_keys=list(recipe.env_keys),
        )
    if isinstance(recipe, RemoteMcpRecipe):
        return RemoteMcpMode(
            kind="remote_mcp",
            url=recipe.url,
            headers=dict(recipe.headers),
        )
    # PythonLibRecipe
    return PythonLibMode(
        kind="python_lib",
        pip_name=recipe.pip_name,
        pip_version=recipe.pip_version,
        import_module=recipe.import_module,
        instance_factory=InstanceFactory(
            cls=recipe.instance_factory_cls,
            args=dict(recipe.instance_factory_args),
        ),
    )


async def _run_canary_call(
    *,
    launch: dict[str, Any],
    secrets: dict[str, str],
    canary_tool: str,
    canary_args: dict[str, Any],
) -> None:
    """Build a transport from the persisted launch dict and invoke the
    canary tool with sample args. Raises any error from the upstream
    call so callers can demote the connector to FAILED.

    list_tools is not a sufficient auth check: FMP's hosted MCP returns
    its tool list without authentication, so a wrong api_key would pass
    `_validate_launch` silently. The canary forces an authenticated
    round-trip on the same transport before we accept the install.
    """
    selected = _select_mode(launch)
    if selected is None:
        raise RuntimeError("canary skipped: no usable mode")
    transport = _build_transport("<canary>", selected, secrets)
    try:
        await transport.call_tool(canary_tool, dict(canary_args))
    finally:
        try:
            await transport.aclose()
        except Exception:
            pass


async def install_builtin(
    session: Session,
    *,
    template_id: str,
    api_key: str,
) -> Connector:
    """Install a built-in connector from the day-1 catalog without the wizard.

    Raises KeyError when `template_id` is not in the catalog.
    Calls `create_connector` (validation + dept-health invalidation),
    runs the template's canary call (when defined) to confirm the api
    key actually authenticates, then inserts one RunnerCallableSpec
    row per template.runner_specs entry.
    """
    template = get_template(template_id)
    if template is None:
        raise KeyError(f"unknown built-in template: {template_id!r}")

    modes = [_recipe_to_mode(r) for r in template.available_modes]
    launch = LaunchSpec(modes=modes)

    connector = await create_connector(
        session,
        provider_id=template.template_id,
        display_name=template.display_name,
        source=ConnectorSource.BUILT_IN,
        category=template.category,
        launch=launch,
        secrets={template.api_key_env_var: api_key},
    )

    # Canary check — only if list_tools succeeded and the template defines one.
    if (
        connector.status == ConnectorStatus.VALIDATED.value
        and template.canary_tool is not None
        and template.canary_args is not None
    ):
        try:
            await _run_canary_call(
                launch=connector.launch or {},
                secrets=connector.secrets or {},
                canary_tool=template.canary_tool,
                canary_args=dict(template.canary_args),
            )
        except Exception as exc:
            connector.status = ConnectorStatus.FAILED.value
            connector.last_error = f"canary {template.canary_tool!r} failed: {exc}"
            session.commit()
            session.refresh(connector)

    if connector.status == ConnectorStatus.VALIDATED.value and template.runner_specs:
        _upsert_runner_specs_from_template(session, connector.id, template)
        _invalidate(session)

    return connector


def _upsert_runner_specs_from_template(
    session: Session,
    connector_id: str,
    template: BuiltInTemplate,
) -> int:
    """Insert / replace RunnerCallableSpec rows for `connector_id` from
    `template.runner_specs`. Returns the number of specs upserted.

    Day-1 templates can be alternative providers (EODHD vs FMP both
    claim portfolio/stock_quote). The (dept, need) UNIQUE
    constraint forbids two rows for the same key, so we transfer
    ownership: delete any existing row for each (dept, need) this
    template covers, then insert the new spec. The previous owning
    connector row remains live for chat-toolbox use.
    """
    inserted = 0
    for spec in template.runner_specs:
        dept_id = _NEED_DEPARTMENT_MAP.get(spec.need_id)
        if dept_id is None:
            log.warning(
                "sync_template_specs: no department mapping for need %r; skipping",
                spec.need_id,
            )
            continue
        session.query(RunnerCallableSpec).filter(
            RunnerCallableSpec.department_id == dept_id,
            RunnerCallableSpec.need_id == spec.need_id,
        ).delete(synchronize_session=False)
        row = RunnerCallableSpec(
            id=str(uuid.uuid4()),
            department_id=dept_id,
            need_id=spec.need_id,
            connector_id=connector_id,
            access_mode=spec.access_mode,
            spec=asdict(spec),
        )
        session.add(row)
        inserted += 1
    session.commit()
    return inserted


def sync_template_specs(session: Session, connector_id: str) -> int:
    """Re-sync runner_callable_specs for an already-installed built-in
    connector against its template's current runner_specs definition.

    Used when a template gains a new runner spec (or modifies an
    existing one) after the user already installed the connector.
    Without this, those specs only land on fresh installs.

    Raises KeyError when `connector_id` is unknown, or the connector is
    not a built-in, or its provider_id no longer matches any template
    in the registry.
    """
    connector = session.get(Connector, connector_id)
    if connector is None:
        raise KeyError(f"unknown connector: {connector_id!r}")
    if connector.source != ConnectorSource.BUILT_IN.value:
        raise KeyError(
            f"connector {connector_id!r} is not built-in (source={connector.source!r})",
        )
    template = get_template(connector.provider_id)
    if template is None:
        raise KeyError(
            f"no built-in template registered for provider_id={connector.provider_id!r}",
        )
    if not template.runner_specs:
        return 0
    inserted = _upsert_runner_specs_from_template(session, connector.id, template)
    _invalidate(session)
    return inserted


def list_connectors(session: Session) -> list[Connector]:
    return list(session.query(Connector).order_by(Connector.created_at).all())


def get_connector(session: Session, connector_id: str) -> Connector | None:
    return session.get(Connector, connector_id)


async def update_connector(
    session: Session,
    connector_id: str,
    *,
    provider_id: str,
    display_name: str,
    source: ConnectorSource,
    category: Category,
    launch: LaunchSpec | dict[str, Any],
    secrets: dict[str, str] | None,
    source_repo_url: str | None = None,
    source_repo_revision: str | None = None,
    grounding_paths: list[str] | None = None,
    openapi_url: str | None = None,
) -> Connector | None:
    row = session.get(Connector, connector_id)
    if row is None:
        return None
    launch_json = _launch_to_dict(launch)
    row.provider_id = provider_id
    row.display_name = display_name
    row.source = source.value
    row.category = category.value
    row.launch = launch_json
    row.source_repo_url = source_repo_url
    row.source_repo_revision = source_repo_revision
    row.grounding_paths = grounding_paths
    row.openapi_url = openapi_url
    if secrets is not None:
        row.secrets = secrets
    effective_secrets = row.secrets or {}
    result = await _validate_launch(
        launch_json, effective_secrets, tool_overrides=_overrides_for_provider(provider_id)
    )
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
    if row.source_repo_url:
        _trigger_grounding_clone(session, row.id, force=True)
    _invalidate(session)
    return row


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
    result = await _validate_launch(
        row.launch or {},
        row.secrets or {},
        tool_overrides=_overrides_for_provider(row.provider_id),
    )
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
