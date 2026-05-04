from __future__ import annotations

import uuid
from collections.abc import Callable

from openlia.skills.store import Scope
from openlia.skills.types import InstalledSkill, SkillManifest
from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.skills import Skill, SkillUserOverride


class DatabaseSkillStore:
    """User-scope store for company mode (no shell access for users)."""

    def __init__(self, *, session_factory: Callable[[], DBSession]) -> None:
        self._sf = session_factory

    async def list(self, *, scope: Scope, user_id: str | None) -> list[InstalledSkill]:
        with self._sf() as db:
            stmt = select(Skill).where(Skill.scope == scope)
            if scope == "user":
                stmt = stmt.where(Skill.user_id == user_id)
            rows = db.execute(stmt).scalars().all()
            return [self._to_installed(r) for r in rows]

    async def get(
        self, skill_id: str, *, scope: Scope, user_id: str | None
    ) -> InstalledSkill | None:
        with self._sf() as db:
            stmt = select(Skill).where(and_(Skill.scope == scope, Skill.skill_id == skill_id))
            if scope == "user":
                stmt = stmt.where(Skill.user_id == user_id)
            row = db.execute(stmt).scalar_one_or_none()
            return self._to_installed(row) if row else None

    async def install(
        self,
        source: str,
        *,
        scope: Scope,
        user_id: str | None,
        body: str,
        manifest: SkillManifest,
    ) -> InstalledSkill:
        with self._sf() as db:
            existing = db.execute(
                select(Skill).where(
                    and_(
                        Skill.scope == scope,
                        Skill.skill_id == manifest.name,
                        Skill.user_id == (user_id if scope == "user" else None),
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise FileExistsError(
                    f"Skill '{manifest.name}' already installed in scope '{scope}'"
                )
            row = Skill(
                id=str(uuid.uuid4()),
                skill_id=manifest.name,
                scope=scope,
                user_id=user_id if scope == "user" else None,
                frontmatter=manifest.model_dump(exclude_none=True),
                body=body,
                enabled=True,
                source=source,
                version=manifest.version,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_installed(row)

    async def uninstall(self, skill_id: str, *, scope: Scope, user_id: str | None) -> None:
        with self._sf() as db:
            stmt = delete(Skill).where(and_(Skill.scope == scope, Skill.skill_id == skill_id))
            if scope == "user":
                stmt = stmt.where(Skill.user_id == user_id)
            res = db.execute(stmt)
            if res.rowcount == 0:
                raise FileNotFoundError(f"Skill '{skill_id}' not installed in scope '{scope}'")
            db.commit()

    async def set_enabled(
        self, skill_id: str, enabled: bool, *, scope: Scope, user_id: str | None
    ) -> None:
        with self._sf() as db:
            if scope == "system":
                if user_id is None:
                    raise ValueError("user_id required to override a system skill")
                ov = db.execute(
                    select(SkillUserOverride).where(
                        and_(
                            SkillUserOverride.user_id == user_id,
                            SkillUserOverride.skill_id == skill_id,
                        )
                    )
                ).scalar_one_or_none()
                if ov is None:
                    ov = SkillUserOverride(user_id=user_id, skill_id=skill_id, enabled=enabled)
                    db.add(ov)
                else:
                    ov.enabled = enabled
                db.commit()
                return
            row = db.execute(
                select(Skill).where(
                    and_(
                        Skill.scope == scope,
                        Skill.skill_id == skill_id,
                        Skill.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise FileNotFoundError(skill_id)
            row.enabled = enabled
            db.commit()

    @staticmethod
    def _to_installed(row: Skill) -> InstalledSkill:
        manifest = SkillManifest(**row.frontmatter)
        return InstalledSkill(
            manifest=manifest,
            body=row.body,
            scope=row.scope,  # type: ignore[arg-type]
            user_id=row.user_id,
            enabled=row.enabled,
            installed_at=row.installed_at,
            source=row.source,
        )
