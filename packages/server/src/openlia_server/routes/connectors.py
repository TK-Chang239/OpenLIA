"""Routes for the connector subsystem under /connectors.

V2 (connector-redesign-v2): the request/response models track the
multi-mode `LaunchSpec` shape. Each mode dict matches `{"kind": ...,
... mode-specific fields ...}`.
"""

from __future__ import annotations

import importlib
import inspect
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.connectors.types import Category, ConnectorSource
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.auth import build_require_active_admin
from openlia_server.services import connectors_service


class ModeIn(BaseModel):
    kind: str
    # cli_mcp
    argv: list[str] | None = None
    env_keys: list[str] | None = None
    # remote_mcp
    url: str | None = None
    headers: dict[str, str] | None = None
    # python_lib
    pip_name: str | None = None
    pip_version: str | None = None
    import_module: str | None = None
    instance_factory: dict[str, Any] | None = None


class LaunchIn(BaseModel):
    modes: list[ModeIn]


class ConnectorCreate(BaseModel):
    provider_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    source: str = Field(pattern="^(built_in|remote_mcp|cli_mcp|python_lib|skill)$")
    category: str = Field(pattern="^(financial|news|social|web_search)$")
    launch: LaunchIn
    secrets: dict[str, str] | None = None
    source_repo_url: str | None = None
    source_repo_revision: str | None = None
    openapi_url: str | None = None


class ConnectorUpdate(ConnectorCreate):
    pass


class IntrospectPythonLibIn(BaseModel):
    import_module: str = Field(min_length=1, max_length=128)
    cls: str = Field(min_length=1, max_length=128)


# Strict, conservative pattern: must start with a letter or digit, then
# letters/digits/dots/underscores/hyphens. Excludes flags ("-…"), URLs,
# paths, shell metas. Mirrors PEP 508 distribution-name shape.
_PIP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# Only the standard PEP 440 prefix operators followed by a version-ish tail.
_PIP_VERSION_RE = re.compile(r"^(==|>=|<=|~=|!=|>|<)?[A-Za-z0-9.+!*-]{0,32}$")


class InstallPythonPackageIn(BaseModel):
    pip_name: str = Field(min_length=1, max_length=64)
    pip_version: str = Field(default="", max_length=32)


class InstallPythonPackageOut(BaseModel):
    stdout: str


class ParamSpec(BaseModel):
    name: str
    type: str | None
    required: bool
    default: Any | None = None


class IntrospectPythonLibOut(BaseModel):
    params: list[ParamSpec]


def _annotation_str(ann: Any) -> str | None:
    if ann is inspect.Parameter.empty:
        return None
    try:
        if hasattr(ann, "__name__"):
            return str(ann.__name__)
        return str(ann)
    except Exception:
        return None


def _introspect_init(import_module: str, cls_name: str) -> list[ParamSpec]:
    """Return the kwarg list for `cls_name.__init__`, skipping `self`.

    Raises HTTPException(400) with an actionable message when the module is
    not installed or the class is not found.
    """
    try:
        mod = importlib.import_module(import_module)
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Module '{import_module}' is not installed in the server's "
                f"Python environment. Run `pip install <package>` in that "
                f"environment, restart the server, then click Detect again. "
                f"({exc})"
            ),
        ) from exc
    try:
        cls = getattr(mod, cls_name)
    except AttributeError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Module '{import_module}' has no attribute '{cls_name}'. "
                f"Check the library's docs for the correct class name."
            ),
        ) from exc
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not introspect '{cls_name}.__init__': {exc}",
        ) from exc

    params: list[ParamSpec] = []
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        default: Any | None = None
        if p.default is not inspect.Parameter.empty:
            try:
                # Round-trip via repr so dataclasses / sentinels don't
                # break JSON serialization. Only commit primitive defaults.
                if isinstance(p.default, (str, int, float, bool, type(None))):
                    default = p.default
                else:
                    default = repr(p.default)
            except Exception:
                default = None
        params.append(
            ParamSpec(
                name=p.name,
                type=_annotation_str(p.annotation),
                required=p.default is inspect.Parameter.empty,
                default=default,
            )
        )
    return params


class ConnectorOut(BaseModel):
    id: str
    provider_id: str
    display_name: str
    source: str
    category: str
    status: str
    last_error: str | None
    cached_tools_count: int


class ConnectorDetail(ConnectorOut):
    launch: dict[str, Any]
    secret_keys: list[str]
    source_repo_url: str | None = None
    source_repo_revision: str | None = None
    openapi_url: str | None = None
    grounding_status: str = "none"
    cached_repo_commit_sha: str | None = None


def _to_out(row: Any) -> ConnectorOut:
    tools = row.cached_tools or []
    return ConnectorOut(
        id=row.id,
        provider_id=row.provider_id,
        display_name=row.display_name,
        source=row.source,
        category=row.category,
        status=row.status,
        last_error=row.last_error,
        cached_tools_count=len(tools),
    )


def _to_detail(row: Any) -> ConnectorDetail:
    base = _to_out(row)
    return ConnectorDetail(
        **base.model_dump(),
        launch=row.launch or {"modes": []},
        secret_keys=sorted((row.secrets or {}).keys()),
        source_repo_url=row.source_repo_url,
        source_repo_revision=row.source_repo_revision,
        openapi_url=row.openapi_url,
        grounding_status=row.grounding_status or "none",
        cached_repo_commit_sha=row.cached_repo_commit_sha,
    )


def build_connectors_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"] = "personal",
) -> APIRouter:
    """Mount the connector subsystem under /connectors.

    The router as a whole is gated by `require_active_admin`. In personal
    mode that dependency resolves to the synthetic `local` user with no
    cookie required, so the wizard's existing fetches work unchanged. In
    company mode, every /api/connectors/* route requires a valid session
    cookie tied to a user with `is_admin = true`.
    """
    require_admin = build_require_active_admin(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(
        prefix="/connectors",
        tags=["connectors"],
        dependencies=[require_admin],
    )
    session_dep = make_session_dependency(db_session_factory)

    @router.post(
        "/introspect-python-lib",
        response_model=IntrospectPythonLibOut,
    )
    def introspect_python_lib(body: IntrospectPythonLibIn) -> IntrospectPythonLibOut:
        params = _introspect_init(body.import_module, body.cls)
        return IntrospectPythonLibOut(params=params)

    @router.post(
        "/install-python-package",
        response_model=InstallPythonPackageOut,
    )
    def install_python_package(
        body: InstallPythonPackageIn,
    ) -> InstallPythonPackageOut:
        """Install a package into the server's own interpreter.

        Admin-only (router-level dependency). Inputs are restricted to a
        plain PEP 508 name + PEP 440 version tail; URL/path installs and
        flag-smuggling are refused before subprocess runs. After a successful
        install we invalidate the import cache so a subsequent
        `introspect-python-lib` call sees the freshly installed module
        without a server restart.

        Prefers `uv pip install --python <sys.executable>` because uv-managed
        venvs ship without pip bootstrapped. Falls back to
        `python -m pip install` when uv is not on PATH.
        """
        if not _PIP_NAME_RE.match(body.pip_name):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid pip name. Use a plain package name (letters, digits, '.', '_', '-')."
                ),
            )
        if body.pip_version and not _PIP_VERSION_RE.match(body.pip_version):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid pip version. Use a PEP 440 specifier like "
                    "'==1.2.3', '>=2.0', or leave blank for latest."
                ),
            )
        spec = f"{body.pip_name}{body.pip_version or ''}"
        uv_path = shutil.which("uv")
        if uv_path is not None:
            args = [uv_path, "pip", "install", "--python", sys.executable, spec]
        else:
            args = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                spec,
            ]
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=(proc.stderr or proc.stdout).strip()
                or f"install {spec} failed (exit {proc.returncode}).",
            )
        importlib.invalidate_caches()
        return InstallPythonPackageOut(stdout=proc.stdout or proc.stderr)

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=ConnectorOut)
    async def create(body: ConnectorCreate, db: DBSession = Depends(session_dep)) -> ConnectorOut:
        launch_dict = body.launch.model_dump(exclude_none=True)
        row = await connectors_service.create_connector(
            db,
            provider_id=body.provider_id,
            display_name=body.display_name,
            source=ConnectorSource(body.source),
            category=Category(body.category),
            launch=launch_dict,
            secrets=body.secrets,
            source_repo_url=body.source_repo_url,
            source_repo_revision=body.source_repo_revision,
            openapi_url=body.openapi_url,
        )
        return _to_out(row)

    @router.get("", response_model=list[ConnectorOut])
    def list_(db: DBSession = Depends(session_dep)) -> list[ConnectorOut]:
        return [_to_out(r) for r in connectors_service.list_connectors(db)]

    @router.get("/{connector_id}", response_model=ConnectorDetail)
    def get(connector_id: str, db: DBSession = Depends(session_dep)) -> ConnectorDetail:
        row = connectors_service.get_connector(db, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        return _to_detail(row)

    @router.put("/{connector_id}", response_model=ConnectorOut)
    async def update(
        connector_id: str,
        body: ConnectorUpdate,
        db: DBSession = Depends(session_dep),
    ) -> ConnectorOut:
        launch_dict = body.launch.model_dump(exclude_none=True)
        row = await connectors_service.update_connector(
            db,
            connector_id,
            provider_id=body.provider_id,
            display_name=body.display_name,
            source=ConnectorSource(body.source),
            category=Category(body.category),
            launch=launch_dict,
            secrets=body.secrets,
            source_repo_url=body.source_repo_url,
            source_repo_revision=body.source_repo_revision,
            openapi_url=body.openapi_url,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        return _to_out(row)

    @router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(connector_id: str, db: DBSession = Depends(session_dep)) -> None:
        connectors_service.delete_connector(db, connector_id)

    @router.post("/{connector_id}/validate", response_model=ConnectorOut)
    async def revalidate(connector_id: str, db: DBSession = Depends(session_dep)) -> ConnectorOut:
        row = await connectors_service.revalidate_connector(db, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        return _to_out(row)

    return router
