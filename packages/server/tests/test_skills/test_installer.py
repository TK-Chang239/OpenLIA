import io
import zipfile

import pytest
from openlia_server.services.skill_installer import (
    install_from_folder,
    install_from_zip,
)

SAMPLE = """---
name: zipped
description: Zip skill.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


def _make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("zipped/SKILL.md", SAMPLE)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_install_from_zip_writes_skill(tmp_path):
    fs_store, _ = _make_stores(tmp_path)
    installed = await install_from_zip(fs_store, scope="user", user_id="u1", zip_bytes=_make_zip())
    assert installed.manifest.name == "zipped"
    got = await fs_store.get("zipped", scope="user", user_id="u1")
    assert got is not None


@pytest.mark.asyncio
async def test_install_from_folder_path(tmp_path):
    src = tmp_path / "src" / "alpha"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(SAMPLE.replace("zipped", "alpha"))
    fs_store, _ = _make_stores(tmp_path)
    installed = await install_from_folder(fs_store, scope="user", user_id="u1", folder_path=src)
    assert installed.manifest.name == "alpha"


def _make_stores(tmp_path):
    from openlia.skills import FilesystemSkillStore

    return FilesystemSkillStore(root=tmp_path / "store"), tmp_path
