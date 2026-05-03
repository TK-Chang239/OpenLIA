from __future__ import annotations

import asyncio
import io
import tempfile
import zipfile
from pathlib import Path

from openlia.skills import (
    InstalledSkill,
    SkillStore,
    parse_skill_md,
)

_MAX_ZIP_BYTES = 5 * 1024 * 1024


async def install_from_folder(
    store: SkillStore,
    *,
    scope: str,
    user_id: str | None,
    folder_path: Path,
) -> InstalledSkill:
    md_path = folder_path / "SKILL.md"
    if not md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in {folder_path}")
    manifest, body = parse_skill_md(md_path.read_text())
    return await store.install(
        source=f"folder:{folder_path}",
        scope=scope,
        user_id=user_id,
        body=body,
        manifest=manifest,
    )


async def install_from_zip(
    store: SkillStore,
    *,
    scope: str,
    user_id: str | None,
    zip_bytes: bytes,
) -> InstalledSkill:
    if len(zip_bytes) > _MAX_ZIP_BYTES:
        raise ValueError("zip exceeds 5 MB cap")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extractall(tmp_path)
        # Find a SKILL.md anywhere in the archive.
        md = next(tmp_path.rglob("SKILL.md"), None)
        if md is None:
            raise FileNotFoundError("zip contains no SKILL.md")
        return await install_from_folder(store, scope=scope, user_id=user_id, folder_path=md.parent)


async def install_from_git(
    store: SkillStore,
    *,
    scope: str,
    user_id: str | None,
    git_url: str,
    ref: str | None = None,
) -> InstalledSkill:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "clone"
        cmd = ["git", "clone", "--depth", "1"]
        if ref:
            cmd += ["--branch", ref]
        cmd += [git_url, str(tmp_path)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"git clone failed (exit {proc.returncode}): {stderr.decode().strip()}"
            )
        md = next(tmp_path.rglob("SKILL.md"), None)
        if md is None:
            raise FileNotFoundError(f"{git_url} contains no SKILL.md")
        manifest, body = parse_skill_md(md.read_text())
        return await store.install(
            source=f"git:{git_url}" + (f"#{ref}" if ref else ""),
            scope=scope,
            user_id=user_id,
            body=body,
            manifest=manifest,
        )
