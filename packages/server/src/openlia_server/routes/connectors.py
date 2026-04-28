"""Routes for the connector subsystem under /connectors.

V2 (connector-redesign-v2): the request/response models track the
multi-mode `LaunchSpec` shape. Each mode dict matches `{"kind": ...,
... mode-specific fields ...}`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.connectors.types import Category, ConnectorSource
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
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


class ConnectorOut(BaseModel):
    id: str
    provider_id: str
    display_name: str
    source: str
    category: str
    status: str
    last_error: str | None
    cached_tools_count: int


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


def build_connectors_router(*, db_session_factory: Callable[[], DBSession]) -> APIRouter:
    router = APIRouter(prefix="/connectors", tags=["connectors"])
    session_dep = make_session_dependency(db_session_factory)

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
        )
        return _to_out(row)

    @router.get("", response_model=list[ConnectorOut])
    def list_(db: DBSession = Depends(session_dep)) -> list[ConnectorOut]:
        return [_to_out(r) for r in connectors_service.list_connectors(db)]

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
