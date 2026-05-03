from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from openlia.skills.types import InstalledSkill, SkillManifest

Scope = Literal["system", "user"]


@runtime_checkable
class SkillStore(Protocol):
    async def list(self, *, scope: Scope, user_id: str | None) -> list[InstalledSkill]: ...

    async def get(
        self, skill_id: str, *, scope: Scope, user_id: str | None
    ) -> InstalledSkill | None: ...

    async def install(
        self,
        source: str,
        *,
        scope: Scope,
        user_id: str | None,
        body: str,
        manifest: SkillManifest,
    ) -> InstalledSkill: ...

    async def uninstall(self, skill_id: str, *, scope: Scope, user_id: str | None) -> None: ...

    async def set_enabled(
        self, skill_id: str, enabled: bool, *, scope: Scope, user_id: str | None
    ) -> None: ...


@dataclass
class LayeredSkillStore:
    system: SkillStore
    user: SkillStore

    def for_scope(self, scope: Scope) -> SkillStore:
        return self.system if scope == "system" else self.user

    async def list_visible(
        self, *, user_id: str | None, scope_filter: Scope | None = None
    ) -> list[InstalledSkill]:
        out: list[InstalledSkill] = []
        if scope_filter in (None, "system"):
            out.extend(await self.system.list(scope="system", user_id=None))
        if scope_filter in (None, "user"):
            out.extend(await self.user.list(scope="user", user_id=user_id))
        return out
