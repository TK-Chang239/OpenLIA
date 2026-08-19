"""Panic Thermometer department routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from openlia.formula import FormulaError
from openlia.formula.parser import parse as _parse_formula
from openlia.formula.requirements import extract_requirements
from pydantic import BaseModel, Field

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import PtPreset
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import pt_dash_cache
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import PtRunner


class _ConfigDTO(BaseModel):
    panel_config: list[dict[str, Any]]
    composite_settings: dict[str, Any] = Field(default_factory=dict)
    active_preset_id: str | None = None


class _PresetCreateDTO(BaseModel):
    name: str
    description: str | None = None


class _PresetUpdateDTO(BaseModel):
    name: str
    description: str | None = None


class _FormulaParseDTO(BaseModel):
    formula: str
    panel: str


class _FormulaTestDTO(BaseModel):
    formula: str
    panel: str
    params: dict[str, Any] = Field(default_factory=dict)


class _RulesetPreviewDTO(BaseModel):
    panel: str
    ruleset: dict[str, Any]


def _preset_out(row: PtPreset) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "description": row.description,
        "is_shipped": row.is_shipped,
    }


def _config_out(cfg: Any) -> dict[str, Any]:
    return {
        "id": cfg.id,
        "panel_config": cfg.panel_config,
        "composite_settings": cfg.composite_settings,
        "active_preset_id": cfg.active_preset_id,
    }


def build_panic_thermometer_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
) -> APIRouter:
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/departments/panic_thermometer", tags=["panic_thermometer"])

    def _config_service() -> PtConfigService:
        return PtConfigService(session_factory=db_session_factory)

    def _runner_dep(request: Request) -> PtRunner:
        runner = getattr(request.app.state, "pt_runner", None)
        if runner is None:
            raise HTTPException(
                status_code=503,
                detail="panic thermometer runner not wired",
            )
        return runner

    def _invalidate_dashboard_cache(user_id: str) -> None:
        with db_session_factory() as s:
            pt_dash_cache.invalidate(s, user_id)
            s.commit()

    @router.get("/dashboard")
    def get_dashboard(
        user: User = require_auth,
        runner: PtRunner = Depends(_runner_dep),
    ) -> dict[str, Any]:
        # Serve the persisted snapshot when fresh — a full compute costs
        # ~12 upstream calls. The pt_dash scheduler job keeps rows warm,
        # so even a first load after a restart is usually instant.
        with db_session_factory() as s:
            cached, generated_at = pt_dash_cache.read_cache(s, user.id)
        if cached is not None and pt_dash_cache.is_fresh(generated_at):
            return cached

        payload = runner.compute_dashboard(user.id)
        data = pt_dash_cache.payload_to_dict(payload)
        with db_session_factory() as s:
            pt_dash_cache.upsert_cache(s, user.id, data)
            s.commit()
        return data

    @router.get("/config")
    def get_config(user: User = require_auth) -> dict[str, Any]:
        cfg = _config_service().get_or_create_for_user(user.id)
        return _config_out(cfg)

    @router.put("/config")
    def put_config(payload: _ConfigDTO, user: User = require_auth) -> dict[str, Any]:
        cfg = _config_service().update_config(
            user.id,
            panel_config=payload.panel_config,
            composite_settings=payload.composite_settings,
        )
        # A ruleset change makes the cached dashboard wrong; recompute on
        # the next read.
        _invalidate_dashboard_cache(user.id)
        return _config_out(cfg)

    @router.get("/config/export")
    def export_config(user: User = require_auth) -> dict[str, Any]:
        return _config_service().export_config(user.id)

    @router.post("/config/import")
    def import_config(
        payload: dict[str, Any],
        user: User = require_auth,
    ) -> dict[str, Any]:
        try:
            cfg = _config_service().import_config(user.id, payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        _invalidate_dashboard_cache(user.id)
        return _config_out(cfg)

    @router.get("/presets")
    def list_presets(user: User = require_auth) -> list[dict[str, Any]]:
        return [_preset_out(r) for r in _config_service().list_presets(user.id)]

    @router.post("/presets", status_code=201)
    def create_preset(payload: _PresetCreateDTO, user: User = require_auth) -> dict[str, Any]:
        return _preset_out(
            _config_service().create_preset(
                user.id, name=payload.name, description=payload.description
            )
        )

    @router.put("/presets/{preset_id}")
    def update_preset(
        preset_id: str,
        payload: _PresetUpdateDTO,
        user: User = require_auth,
    ) -> dict[str, Any]:
        try:
            return _preset_out(
                _config_service().update_preset(
                    user.id,
                    preset_id,
                    name=payload.name,
                    description=payload.description,
                )
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.delete("/presets/{preset_id}", status_code=204)
    def delete_preset(preset_id: str, user: User = require_auth) -> None:
        try:
            _config_service().delete_preset(user.id, preset_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.post("/presets/{preset_id}/apply")
    def apply_preset(preset_id: str, user: User = require_auth) -> dict[str, Any]:
        try:
            cfg = _config_service().apply_preset(user.id, preset_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        _invalidate_dashboard_cache(user.id)
        return _config_out(cfg)

    @router.post("/formula/parse")
    def formula_parse(payload: _FormulaParseDTO, user: User = require_auth) -> dict[str, Any]:
        try:
            _parse_formula(payload.formula)
            identifiers = [
                getattr(r, "name", None) or str(r) for r in extract_requirements(payload.formula)
            ]
            return {
                "ok": True,
                "identifiers": identifiers,
                "unknown_identifiers": [],
                "warnings": [],
            }
        except FormulaError as exc:
            return {
                "ok": False,
                "errors": [
                    {
                        "type": "parse",
                        "message": str(exc),
                        "position": 0,
                    }
                ],
            }

    @router.post("/formula/test")
    def formula_test(
        payload: _FormulaTestDTO,
        user: User = require_auth,
        runner: PtRunner = Depends(_runner_dep),
    ) -> dict[str, Any]:
        try:
            result = runner.test_formula(
                user.id,
                payload.panel,
                payload.formula,
                params_override=payload.params,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except FormulaError as exc:
            return {
                "value": None,
                "resolved_values": {},
                "errors": [{"type": "eval", "message": str(exc)}],
                "warnings": [],
            }
        return {
            "value": result.value,
            "resolved_values": result.resolved_values,
            "errors": [],
            "warnings": result.warnings,
        }

    @router.post("/ruleset/preview")
    def ruleset_preview(
        payload: _RulesetPreviewDTO,
        user: User = require_auth,
        runner: PtRunner = Depends(_runner_dep),
    ) -> dict[str, Any]:
        try:
            r = runner.preview_ruleset(user.id, payload.panel, payload.ruleset)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {
            "status": r.status,
            "matched_rule_index": r.matched_rule_index,
            "label": r.label,
            "resolved_values": r.resolved_values,
            "derived_scalars": r.derived_scalars,
            "warnings": r.warnings,
        }

    return router
