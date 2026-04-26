"""Routes for the connector subsystem under /connectors (mounted under /api by the app)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.connectors.types import Category, ConnectorSource, MCPLaunchSpec
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.services import connectors_service


class LaunchIn(BaseModel):
    kind: str
    url: str | None = None
    headers: dict[str, str] | None = None
    argv: list[str] | None = None
    env: dict[str, str] | None = None
    template_id: str | None = None


class ConnectorCreate(BaseModel):
    provider_id: str = Field(min_length=1, max_length=64)
    source: str = Field(pattern="^(built_in|remote_mcp|cli_mcp)$")
    category: str = Field(pattern="^(financial|news|social|web_search)$")
    launch: LaunchIn
    credentials_ref: str | None = None


class ConnectorOut(BaseModel):
    id: str
    provider_id: str
    source: str
    category: str
    status: str
    last_error: str | None
    cached_tools_count: int


class ScopeRequestIn(BaseModel):
    connector_ids: list[str] | None = None


class ScopeResponseRow(BaseModel):
    connector_id: str
    rows_written: int


class ScopeResponse(BaseModel):
    scoped: int
    per_connector: list[ScopeResponseRow]


def _to_out(row: Any) -> ConnectorOut:
    tools = row.cached_tools or []
    return ConnectorOut(
        id=row.id,
        provider_id=row.provider_id,
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
        spec = MCPLaunchSpec.from_json(body.launch.model_dump(exclude_none=True))
        row = await connectors_service.create_connector(
            db,
            provider_id=body.provider_id,
            source=ConnectorSource(body.source),
            category=Category(body.category),
            launch=spec,
            credentials_ref=body.credentials_ref,
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

    @router.post("/review/scope", response_model=ScopeResponse)
    async def scope(body: ScopeRequestIn, db: DBSession = Depends(session_dep)) -> ScopeResponse:
        from openlia.departments import get_all_requirements

        from openlia_server.services.scope_llm_client import QuickTierScopeClient

        counts = await connectors_service.scope_connectors(
            db,
            connector_ids=body.connector_ids,
            llm=QuickTierScopeClient(db),
            requirements=get_all_requirements(),
        )
        return ScopeResponse(
            scoped=sum(counts.values()),
            per_connector=[
                ScopeResponseRow(connector_id=k, rows_written=v) for k, v in counts.items()
            ],
        )

    return router
