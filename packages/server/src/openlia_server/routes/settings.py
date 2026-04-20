"""/settings/* HTTP routes.

Plan 3 adds only the data-providers sub-router. Plan 4 will add the LLM
providers sub-router in the same file; Plan 11 extends further.
"""

import os
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from openlia.data.types import ProviderCategory, ProviderMode
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
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
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/settings/data-providers",
        tags=["settings", "data-providers"],
    )

    # --- collection routes (static paths first) ---

    @router.get("")
    def list_providers(_admin=require_admin, session: DBSession = Depends(session_dep)) -> dict:
        rows = svc.list_providers(session)
        return {"providers": [_row_to_out(r).model_dump() for r in rows]}

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_provider(
        body: _CreateDataProviderIn,
        _admin=require_admin,
        session: DBSession = Depends(session_dep),
    ) -> dict:
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
    def auto_map_endpoint(_admin=require_admin, session: DBSession = Depends(session_dep)) -> dict:
        from openlia.data.manifest import load_manifest

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
    def list_mappings(_admin=require_admin, session: DBSession = Depends(session_dep)) -> dict:
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
    def set_mapping(
        requirement_type: str,
        body: dict,
        _admin=require_admin,
        session: DBSession = Depends(session_dep),
    ) -> dict:
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
    def delete_mapping(
        requirement_type: str,
        provider_id: str,
        _admin=require_admin,
        session: DBSession = Depends(session_dep),
    ) -> Response:
        svc.delete_requirement_mapping(
            session,
            requirement_type=requirement_type,
            provider_id=provider_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # --- per-provider routes (dynamic /{provider_id} paths registered last) ---

    @router.patch("/{provider_id}")
    def update_provider(
        provider_id: str,
        body: _UpdateDataProviderIn,
        _admin=require_admin,
        session: DBSession = Depends(session_dep),
    ) -> dict:
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
    def delete_provider(
        provider_id: str,
        _admin=require_admin,
        session: DBSession = Depends(session_dep),
    ) -> Response:
        try:
            svc.delete_provider(session, provider_id)
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{provider_id}/test-connection")
    async def test_connection(
        provider_id: str,
        _admin=require_admin,
        session: DBSession = Depends(session_dep),
    ) -> dict:
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


# --- LLM provider admin router ------------------------------------------------

from openlia.llm.adapters import build_adapter  # noqa: E402
from openlia.llm.types import Capabilities, ProviderCredentials  # noqa: E402

from openlia_server.services import llm_providers as llm_svc  # noqa: E402


class _ProviderIn(BaseModel):
    kind: Literal["openai", "anthropic", "gemini", "openrouter", "openai_compat", "ollama"]
    label: str
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None
    extra_config: dict | None = None
    is_enabled: bool = True
    run_test: bool = False
    test_model: str | None = None


class _ProviderOut(BaseModel):
    model_config = {"protected_namespaces": ()}

    id: str
    kind: str
    label: str
    has_api_key: bool
    env_var_name: str | None
    base_url: str | None
    is_enabled: bool
    test: dict | None = None


class _ProviderUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None
    extra_config: dict | None = None
    is_enabled: bool | None = None


class _ModelIn(BaseModel):
    provider_id: str
    tier: Literal["thinking", "everyday", "quick"]
    model_ref: str
    display_name: str
    is_tier_default: bool = False
    is_enabled: bool = True
    overrides: dict | None = None


class _ModelOut(BaseModel):
    id: str
    provider_id: str
    tier: str
    model_ref: str
    display_name: str
    is_tier_default: bool
    is_enabled: bool
    overrides: dict | None


class _TestIn(BaseModel):
    kind: Literal["openai", "anthropic", "gemini", "openrouter", "openai_compat", "ollama"]
    api_key: str | None = None
    base_url: str | None = None
    model: str
    env_var_name: str | None = None


class _TestOut(BaseModel):
    ok: bool
    latency_ms: int
    error_class: str | None = None
    error_msg: str | None = None


class _DepartmentTierIn(BaseModel):
    tier: Literal["thinking", "everyday", "quick"] | None = None


def _provider_to_out(row, *, test: dict | None = None) -> _ProviderOut:
    return _ProviderOut(
        id=row.id,
        kind=row.kind,
        label=row.label,
        has_api_key=bool(row.api_key_encrypted or row.env_var_name),
        env_var_name=row.env_var_name,
        base_url=row.base_url,
        is_enabled=row.is_enabled,
        test=test,
    )


async def _run_connection_test(
    kind: str,
    *,
    api_key: str | None,
    base_url: str | None,
    env_var_name: str | None,
    model: str,
) -> _TestOut:
    effective_key = api_key
    if env_var_name:
        effective_key = os.environ.get(env_var_name) or api_key

    try:
        adapter = build_adapter(
            kind=kind,
            credentials=ProviderCredentials(api_key=effective_key, base_url=base_url),
            model=model,
            capabilities=Capabilities(),
        )
    except Exception as exc:
        return _TestOut(
            ok=False,
            latency_ms=0,
            error_class=type(exc).__name__,
            error_msg=str(exc),
        )

    result = await adapter.test_connection(model)
    return _TestOut(
        ok=result.ok,
        latency_ms=result.latency_ms,
        error_class=result.error_class,
        error_msg=result.error_msg,
    )


def build_llm_providers_admin_router(
    *,
    db_session_factory,
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/settings/admin/llm", tags=["llm-admin"])
    require_admin = build_require_admin(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    # NOTE: static sub-paths (/providers/test, /models) must be registered before
    # dynamic paths (/providers/{provider_id}) to avoid mis-routing.

    @router.get("/providers", response_model=list[_ProviderOut])
    def list_providers(_=require_admin, db: DBSession = Depends(session_dep)) -> list[_ProviderOut]:
        return [_provider_to_out(r) for r in llm_svc.list_providers(db)]

    @router.post("/providers/test", response_model=_TestOut)
    async def test_provider(payload: _TestIn, _=require_admin) -> _TestOut:
        return await _run_connection_test(
            payload.kind,
            api_key=payload.api_key,
            base_url=payload.base_url,
            env_var_name=payload.env_var_name,
            model=payload.model,
        )

    @router.post(
        "/providers",
        response_model=_ProviderOut,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_provider(
        payload: _ProviderIn,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> _ProviderOut:
        test_result: _TestOut | None = None
        if payload.run_test:
            if not payload.test_model:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "test_model required when run_test=true"},
                )
            test_result = await _run_connection_test(
                payload.kind,
                api_key=payload.api_key,
                base_url=payload.base_url,
                env_var_name=payload.env_var_name,
                model=payload.test_model,
            )
            if not test_result.ok:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "connection_test_failed",
                        "test": test_result.model_dump(),
                    },
                )
        created = llm_svc.create_provider(
            db,
            kind=payload.kind,
            label=payload.label,
            api_key=payload.api_key,
            base_url=payload.base_url,
            env_var_name=payload.env_var_name,
            extra_config=payload.extra_config,
            is_enabled=payload.is_enabled,
        )
        row = llm_svc.get_provider(db, created.id)
        return _provider_to_out(row, test=test_result.model_dump() if test_result else None)

    @router.put("/providers/{provider_id}", response_model=_ProviderOut)
    def update_provider(
        provider_id: str,
        payload: _ProviderUpdate,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> _ProviderOut:
        try:
            llm_svc.update_provider(
                db,
                provider_id,
                label=payload.label,
                api_key=payload.api_key,
                base_url=payload.base_url,
                env_var_name=payload.env_var_name,
                extra_config=payload.extra_config,
                is_enabled=payload.is_enabled,
            )
        except llm_svc.ProviderNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            ) from exc
        return _provider_to_out(llm_svc.get_provider(db, provider_id))

    @router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_provider(
        provider_id: str,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> None:
        try:
            llm_svc.delete_provider(db, provider_id)
        except llm_svc.ProviderHasModelsError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "provider has models; delete them first"},
            ) from exc

    @router.get("/providers/{provider_id}/models", response_model=list[_ModelOut])
    def list_models_for_provider(
        provider_id: str,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> list[_ModelOut]:
        try:
            llm_svc.get_provider(db, provider_id)
        except llm_svc.ProviderNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            ) from exc
        return [
            _ModelOut(
                id=m.id,
                provider_id=m.provider_id,
                tier=m.tier,
                model_ref=m.model_ref,
                display_name=m.display_name,
                is_tier_default=m.is_tier_default,
                is_enabled=m.is_enabled,
                overrides=m.overrides,
            )
            for m in llm_svc.list_models_for_provider(db, provider_id)
        ]

    @router.get("/providers/{provider_id}/remote-models", response_model=list[dict])
    async def remote_models(
        provider_id: str,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> list[dict]:
        try:
            row = llm_svc.get_provider(db, provider_id)
        except llm_svc.ProviderNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            ) from exc
        api_key = llm_svc.get_provider_api_key(db, provider_id)
        adapter = build_adapter(
            kind=row.kind,
            credentials=ProviderCredentials(api_key=api_key, base_url=row.base_url),
            model="",
            capabilities=Capabilities(),
        )
        models = await adapter.list_models()
        return [
            {
                "id": m.id,
                "display_name": m.display_name,
                "context_window": m.context_window,
            }
            for m in models
        ]

    @router.post("/models", response_model=_ModelOut, status_code=status.HTTP_201_CREATED)
    def create_model(
        payload: _ModelIn,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> _ModelOut:
        from openlia_server.db.models.config import LLMModel

        try:
            llm_svc.get_provider(db, payload.provider_id)
        except llm_svc.ProviderNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            ) from exc
        created = llm_svc.create_model(
            db,
            provider_id=payload.provider_id,
            tier=payload.tier,
            model_ref=payload.model_ref,
            display_name=payload.display_name,
            is_tier_default=payload.is_tier_default,
            is_enabled=payload.is_enabled,
            overrides=payload.overrides,
        )
        m = db.get(LLMModel, created.id)
        return _ModelOut(
            id=m.id,
            provider_id=m.provider_id,
            tier=m.tier,
            model_ref=m.model_ref,
            display_name=m.display_name,
            is_tier_default=m.is_tier_default,
            is_enabled=m.is_enabled,
            overrides=m.overrides,
        )

    @router.put("/models/{model_id}", response_model=_ModelOut)
    def update_model(
        model_id: str,
        payload: _ModelIn,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> _ModelOut:
        from openlia_server.db.models.config import LLMModel

        try:
            llm_svc.update_model(
                db,
                model_id,
                display_name=payload.display_name,
                is_tier_default=payload.is_tier_default,
                is_enabled=payload.is_enabled,
                overrides=payload.overrides,
            )
        except llm_svc.ModelNotFoundInDBError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "model not found"},
            ) from exc
        m = db.get(LLMModel, model_id)
        return _ModelOut(
            id=m.id,
            provider_id=m.provider_id,
            tier=m.tier,
            model_ref=m.model_ref,
            display_name=m.display_name,
            is_tier_default=m.is_tier_default,
            is_enabled=m.is_enabled,
            overrides=m.overrides,
        )

    @router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_model(model_id: str, _=require_admin, db: DBSession = Depends(session_dep)) -> None:
        llm_svc.delete_model(db, model_id)

    @router.post("/department/{department_id}")
    def set_department_tier(
        department_id: str,
        payload: _DepartmentTierIn,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> dict:
        if payload.tier is None:
            llm_svc.clear_department_tier_override(db, department_id)
        else:
            llm_svc.set_department_tier_override(db, department_id, payload.tier)
        return {"ok": True}

    @router.post("/capability_override/{provider_kind}/{model:path}")
    def set_capability_override(
        provider_kind: str,
        model: str,
        payload: dict | None = None,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> dict:
        if payload is None:
            llm_svc.clear_capability_override(db, provider_kind=provider_kind, model=model)
        else:
            llm_svc.set_capability_override(
                db,
                provider_kind=provider_kind,
                model=model,
                override=payload,
            )
        return {"ok": True}

    return router
