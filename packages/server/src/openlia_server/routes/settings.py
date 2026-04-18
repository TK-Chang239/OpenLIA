"""/settings/* HTTP routes.

Plan 3 adds only the data-providers sub-router. Plan 4 will add the LLM
providers sub-router in the same file; Plan 11 extends further.
"""

import os
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response, status
from openlia.data.types import ProviderCategory, ProviderMode
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.config import DataProviderRequirementMapping
from openlia_server.middleware.auth import build_require_admin
from openlia_server.services import data_providers as svc


class _CreateDataProviderIn(BaseModel):
    kind: str
    label: str
    category: Literal["financial", "news", "social_media"]
    mode: Literal["api_key", "mcp"]
    api_key: str | None = None
    env_var_name: str | None = None
    base_url: str | None = None
    mcp_url: str | None = None
    extra_config: dict[str, Any] | None = None


class _UpdateDataProviderIn(BaseModel):
    label: str | None = None
    api_key: str | None = None
    env_var_name: str | None = None
    base_url: str | None = None
    extra_config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class _DataProviderOut(BaseModel):
    id: str
    kind: str
    label: str
    base_url: str | None
    env_var_name: str | None
    has_api_key: bool
    is_enabled: bool
    extra_config: dict[str, Any] = Field(default_factory=dict)


def _row_to_out(row) -> _DataProviderOut:
    return _DataProviderOut(
        id=row.id,
        kind=row.kind,
        label=row.label,
        base_url=row.base_url,
        env_var_name=row.env_var_name,
        has_api_key=row.api_key_encrypted is not None,
        is_enabled=row.is_enabled,
        extra_config=row.extra_config or {},
    )


def build_data_providers_router(
    *,
    db_session_factory: Callable[[], DBSession],
) -> APIRouter:
    """Factory for /settings/data-providers/*.

    Route registration order matters: static paths (/auto-map, /mappings/*)
    must be registered before dynamic paths (/{provider_id}) to avoid
    FastAPI matching the static segments as provider IDs.
    """
    mode = os.environ.get("OPENLIA_MODE", "personal")
    require_admin = build_require_admin(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(
        prefix="/settings/data-providers",
        tags=["settings", "data-providers"],
    )

    # --- collection routes (static paths first) ---

    @router.get("")
    def list_providers(_admin=require_admin) -> dict:
        session = db_session_factory()
        rows = svc.list_providers(session)
        return {"providers": [_row_to_out(r).model_dump() for r in rows]}

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_provider(body: _CreateDataProviderIn, _admin=require_admin) -> dict:
        session = db_session_factory()
        try:
            created = svc.create_provider(
                session,
                kind=body.kind,
                label=body.label,
                category=ProviderCategory(body.category),
                mode=ProviderMode(body.mode),
                api_key=body.api_key,
                env_var_name=body.env_var_name,
                base_url=body.base_url,
                extra_config=body.extra_config,
            )
        except svc.UnknownProviderKindError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown_provider_kind", "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_provider", "message": str(exc)},
            ) from exc
        row = svc.get_provider(session, created.id)
        return _row_to_out(row).model_dump()

    @router.post("/auto-map")
    def auto_map_endpoint(_admin=require_admin) -> dict:
        from openlia.data.manifest import load_manifest

        session = db_session_factory()
        summary = svc.auto_map(session, manifest=load_manifest())
        return {
            "mapped": [
                {"requirement_type": m.requirement_type, "provider_id": m.provider_id}
                for m in summary.mapped
            ],
            "unmet": [
                {"requirement_type": u.requirement_type, "department": u.department}
                for u in summary.unmet
            ],
        }

    @router.get("/mappings")
    def list_mappings(_admin=require_admin) -> dict:
        session = db_session_factory()
        rows = list(
            session.scalars(
                select(DataProviderRequirementMapping).order_by(
                    DataProviderRequirementMapping.requirement_type,
                    DataProviderRequirementMapping.priority,
                )
            ).all()
        )
        return {
            "mappings": [
                {
                    "requirement_type": r.requirement_type,
                    "provider_id": r.provider_id,
                    "priority": r.priority,
                }
                for r in rows
            ],
        }

    @router.put("/mappings/{requirement_type}")
    def set_mapping(requirement_type: str, body: dict, _admin=require_admin) -> dict:
        session = db_session_factory()
        provider_id = body.get("provider_id")
        priority = body.get("priority")
        if not isinstance(provider_id, str) or not isinstance(priority, int):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_mapping",
                    "message": "provider_id (str) and priority (int) required",
                },
            )
        try:
            svc.get_provider(session, provider_id)
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        svc.set_requirement_mapping(
            session,
            requirement_type=requirement_type,
            provider_id=provider_id,
            priority=priority,
        )
        return {
            "requirement_type": requirement_type,
            "provider_id": provider_id,
            "priority": priority,
        }

    @router.delete(
        "/mappings/{requirement_type}/{provider_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def delete_mapping(requirement_type: str, provider_id: str, _admin=require_admin) -> Response:
        session = db_session_factory()
        svc.delete_requirement_mapping(
            session,
            requirement_type=requirement_type,
            provider_id=provider_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # --- per-provider routes (dynamic /{provider_id} paths registered last) ---

    @router.patch("/{provider_id}")
    def update_provider(
        provider_id: str, body: _UpdateDataProviderIn, _admin=require_admin
    ) -> dict:
        session = db_session_factory()
        try:
            svc.update_provider(
                session,
                provider_id,
                label=body.label,
                api_key=body.api_key,
                env_var_name=body.env_var_name,
                base_url=body.base_url,
                extra_config=body.extra_config,
                is_enabled=body.is_enabled,
            )
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        row = svc.get_provider(session, provider_id)
        return _row_to_out(row).model_dump()

    @router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_provider(provider_id: str, _admin=require_admin) -> Response:
        session = db_session_factory()
        try:
            svc.delete_provider(session, provider_id)
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{provider_id}/test-connection")
    async def test_connection(provider_id: str, _admin=require_admin) -> dict:
        session = db_session_factory()
        try:
            entry = svc.load_provider_entry(session, provider_id)
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        from openlia.data.adapters import ADAPTERS

        adapter_cls = ADAPTERS.get(entry.kind)
        if adapter_cls is None:
            return {"ok": False}
        adapter = adapter_cls(entry)
        return {"ok": await adapter.health_check()}

    return router
