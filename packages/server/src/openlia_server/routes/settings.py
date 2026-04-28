"""/settings/* HTTP routes.

LLM provider admin router lives here. Legacy data-provider routes were
removed as part of the connector redesign (2026-04-28).
"""

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.llm.adapters import build_adapter
from openlia.llm.types import Capabilities, ProviderCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.middleware.auth import build_require_active_admin
from openlia_server.services import llm_providers as llm_svc

# --- LLM provider admin router ------------------------------------------------


class _ProviderIn(BaseModel):
    kind: Literal["openai", "anthropic", "gemini", "openrouter", "openai_compat", "ollama"]
    label: str
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None
    extra_config: dict | None = None
    is_enabled: bool = True
    run_test: bool = True
    skip_reason: str | None = None
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
    clear_api_key: bool = False
    clear_env_var_name: bool = False


class _ModelIn(BaseModel):
    provider_id: str
    tier: Literal["thinking", "everyday", "quick"]
    model_ref: str
    display_name: str
    is_tier_default: bool = False
    is_enabled: bool = True
    overrides: dict | None = None
    advertised_capabilities: dict | None = None


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
    require_admin = build_require_active_admin(db_session_factory=db_session_factory, mode=mode)
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
        elif not payload.skip_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "run_test=false requires skip_reason"},
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
        unchanged = llm_svc.UNCHANGED

        def _maybe(value, *, clear_flag: bool = False):
            if clear_flag:
                return None
            return unchanged if value is None else value

        try:
            llm_svc.update_provider(
                db,
                provider_id,
                label=_maybe(payload.label),
                api_key=_maybe(payload.api_key, clear_flag=payload.clear_api_key),
                base_url=_maybe(payload.base_url),
                env_var_name=_maybe(payload.env_var_name, clear_flag=payload.clear_env_var_name),
                extra_config=_maybe(payload.extra_config),
                is_enabled=_maybe(payload.is_enabled),
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

    @router.get("/providers/{provider_id}/remote-models")
    async def remote_models(
        provider_id: str,
        _=require_admin,
        db: DBSession = Depends(session_dep),
    ) -> dict | list[dict]:
        try:
            row = llm_svc.get_provider(db, provider_id)
        except llm_svc.ProviderNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            ) from exc
        if row.kind in ("openrouter", "ollama"):
            return {"skipped": True, "reason": "manual entry"}
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
            provider_row = llm_svc.get_provider(db, payload.provider_id)
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
        if provider_row.kind == "openai_compat" and payload.advertised_capabilities is not None:
            llm_svc.set_capability_override(
                db,
                provider_kind="openai_compat",
                model=payload.model_ref,
                override=payload.advertised_capabilities,
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
                provider_id=payload.provider_id,
                tier=payload.tier,
                model_ref=payload.model_ref,
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
