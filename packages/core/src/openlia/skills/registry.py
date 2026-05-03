from __future__ import annotations

from openlia.skills.store import LayeredSkillStore
from openlia.skills.types import InstalledSkill


class SkillRegistry:
    """In-memory cache of installed skills with department + user filtering.

    Call `refresh()` after install/uninstall/toggle to rebuild the cache.
    `visible(...)` returns the subset for a given (department, user).
    """

    def __init__(self, *, store: LayeredSkillStore) -> None:
        self._store = store
        self._system: list[InstalledSkill] = []
        self._user: dict[str | None, list[InstalledSkill]] = {}

    async def refresh(self, *, user_ids: list[str | None] | None = None) -> None:
        self._system = await self._store.system.list(scope="system", user_id=None)
        self._user = {}
        for uid in user_ids or [None]:
            self._user[uid] = await self._store.user.list(scope="user", user_id=uid)

    async def refresh_user(self, user_id: str | None) -> None:
        self._user[user_id] = await self._store.user.list(scope="user", user_id=user_id)

    def visible(self, *, department_id: str, user_id: str | None) -> list[InstalledSkill]:
        out: list[InstalledSkill] = []
        for s in self._system + self._user.get(user_id, []):
            if not s.enabled:
                continue
            depts = s.manifest.departments
            if "*" in depts or department_id in depts:
                out.append(s)
        return out

    def get(self, skill_id: str, *, user_id: str | None) -> InstalledSkill | None:
        for s in self._system + self._user.get(user_id, []):
            if s.manifest.name == skill_id:
                return s
        return None
