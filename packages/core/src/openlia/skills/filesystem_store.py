from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from openlia.skills.parser import parse_skill_md, serialize_skill_md
from openlia.skills.store import Scope
from openlia.skills.types import InstalledSkill, SkillManifest


class FilesystemSkillStore:
    """Backs `<root>/{system,user}/<skill_id>/SKILL.md`. Per-user scoping
    in personal mode collapses to a single user dir; company-mode user
    scope uses DatabaseSkillStore instead."""

    def __init__(self, *, root: Path) -> None:
        self._root = root

    def _scope_dir(self, scope: Scope) -> Path:
        d = self._root / scope
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def list(self, *, scope: Scope, user_id: str | None) -> list[InstalledSkill]:
        out: list[InstalledSkill] = []
        for sub in sorted(self._scope_dir(scope).iterdir()):
            if not sub.is_dir():
                continue
            md = sub / "SKILL.md"
            if not md.exists():
                continue
            try:
                manifest, body = parse_skill_md(md.read_text())
            except Exception:
                continue
            stat = md.stat()
            out.append(
                InstalledSkill(
                    manifest=manifest,
                    body=body,
                    scope=scope,
                    user_id=user_id if scope == "user" else None,
                    enabled=not (sub / ".disabled").exists(),
                    installed_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    source=(sub / ".source").read_text().strip()
                    if (sub / ".source").exists()
                    else "folder",
                )
            )
        return out

    async def get(
        self, skill_id: str, *, scope: Scope, user_id: str | None
    ) -> InstalledSkill | None:
        for s in await self.list(scope=scope, user_id=user_id):
            if s.manifest.name == skill_id:
                return s
        return None

    async def install(
        self,
        source: str,
        *,
        scope: Scope,
        user_id: str | None,
        body: str,
        manifest: SkillManifest,
    ) -> InstalledSkill:
        target = self._scope_dir(scope) / manifest.name
        if target.exists():
            raise FileExistsError(f"Skill '{manifest.name}' already installed in scope '{scope}'")
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(serialize_skill_md(manifest, body))
        (target / ".source").write_text(source + "\n")
        got = await self.get(manifest.name, scope=scope, user_id=user_id)
        if got is None:
            raise RuntimeError(f"install succeeded but get('{manifest.name}') returned None")
        return got

    async def uninstall(self, skill_id: str, *, scope: Scope, user_id: str | None) -> None:
        target = self._scope_dir(scope) / skill_id
        if not target.exists():
            raise FileNotFoundError(f"Skill '{skill_id}' not installed in scope '{scope}'")
        shutil.rmtree(target)

    async def set_enabled(
        self, skill_id: str, enabled: bool, *, scope: Scope, user_id: str | None
    ) -> None:
        target = self._scope_dir(scope) / skill_id
        if not target.exists():
            raise FileNotFoundError(f"Skill '{skill_id}' not installed in scope '{scope}'")
        marker = target / ".disabled"
        if enabled and marker.exists():
            marker.unlink()
        elif not enabled and not marker.exists():
            marker.touch()
