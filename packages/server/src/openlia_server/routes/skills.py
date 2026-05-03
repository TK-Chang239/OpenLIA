from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from openlia.skills import LayeredSkillStore, SkillRegistry
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.skill_audit import (
    record_skill_installed,
    record_skill_toggled,
    record_skill_uninstalled,
)
from openlia_server.services.skill_installer import (
    install_from_folder,
    install_from_git,
    install_from_zip,
)


class TogglePatch(BaseModel):
    enabled: bool


def build_skills_router(
    *,
    db_session_factory: Callable[[], DBSession],
    store: LayeredSkillStore,
    registry: SkillRegistry,
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/skills", tags=["skills"])

    @router.get("")
    async def list_skills(user: User = require_auth):
        sys_skills = await store.system.list(scope="system", user_id=None)
        usr_skills = await store.user.list(scope="user", user_id=user.id)
        return {
            "items": [
                {
                    "skill_id": s.manifest.name,
                    "display_name": s.manifest.display_name or s.manifest.name,
                    "description": s.manifest.description,
                    "version": s.manifest.version,
                    "departments": s.manifest.departments,
                    "scope": s.scope,
                    "enabled": s.enabled,
                    "source": s.source,
                    "installed_at": s.installed_at.isoformat(),
                }
                for s in [*sys_skills, *usr_skills]
            ]
        }

    @router.post("/install")
    async def install(
        scope: str = Form("user"),
        source_type: str = Form(...),
        git_url: str | None = Form(None),
        ref: str | None = Form(None),
        folder_path: str | None = Form(None),
        file: UploadFile | None = File(None),
        user: User = require_auth,
    ):
        if scope == "system" and not getattr(user, "is_admin", False):
            raise HTTPException(403, "system-scope install requires admin")
        target = store.for_scope(scope)  # type: ignore[arg-type]
        try:
            if source_type == "zip":
                if file is None:
                    raise HTTPException(400, "missing zip file")
                installed = await install_from_zip(
                    target, scope=scope, user_id=user.id, zip_bytes=await file.read()
                )
            elif source_type == "git":
                if not git_url:
                    raise HTTPException(400, "missing git_url")
                installed = await install_from_git(
                    target, scope=scope, user_id=user.id, git_url=git_url, ref=ref
                )
            elif source_type == "folder":
                if not folder_path:
                    raise HTTPException(400, "missing folder_path")
                installed = await install_from_folder(
                    target, scope=scope, user_id=user.id, folder_path=Path(folder_path)
                )
            else:
                raise HTTPException(400, f"unknown source_type: {source_type}")
        except (ValueError, FileNotFoundError, RuntimeError, zipfile.BadZipFile) as e:
            raise HTTPException(400, str(e)) from None
        record_skill_installed(
            db_session_factory,
            skill_id=installed.manifest.name,
            scope=scope,
            user_id=user.id,
            source=installed.source,
            version=installed.manifest.version,
        )
        await registry.refresh_user(user.id)
        return {"skill_id": installed.manifest.name, "scope": scope}

    @router.delete("/{skill_id}", status_code=204)
    async def uninstall(skill_id: str, user: User = require_auth):
        target = store.user
        try:
            await target.uninstall(skill_id, scope="user", user_id=user.id)
        except FileNotFoundError:
            raise HTTPException(404, "skill not installed") from None
        record_skill_uninstalled(
            db_session_factory, skill_id=skill_id, scope="user", user_id=user.id
        )
        await registry.refresh_user(user.id)
        return None

    @router.patch("/{skill_id}")
    async def toggle(skill_id: str, body: TogglePatch, user: User = require_auth):
        try:
            await store.user.set_enabled(skill_id, body.enabled, scope="user", user_id=user.id)
            scope = "user"
        except FileNotFoundError:
            await store.system.set_enabled(skill_id, body.enabled, scope="system", user_id=user.id)
            scope = "system"
        record_skill_toggled(
            db_session_factory,
            skill_id=skill_id,
            scope=scope,
            user_id=user.id,
            enabled=body.enabled,
        )
        await registry.refresh_user(user.id)
        return {"skill_id": skill_id, "enabled": body.enabled, "scope": scope}

    @router.get("/{skill_id}/body")
    async def body_for(skill_id: str, user: User = require_auth):
        sys_s = await store.system.get(skill_id, scope="system", user_id=None)
        usr_s = await store.user.get(skill_id, scope="user", user_id=user.id)
        s = usr_s or sys_s
        if s is None:
            raise HTTPException(404, "skill not found")
        return {"skill_id": skill_id, "body": s.body}

    return router
