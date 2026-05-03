import pytest
from openlia.skills import FilesystemSkillStore

SAMPLE = """---
name: alpha
display_name: Alpha
description: A test skill.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


@pytest.fixture
def tmp_root(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "user").mkdir()
    return tmp_path


@pytest.fixture
def installed_alpha(tmp_root):
    skill_dir = tmp_root / "user" / "alpha"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SAMPLE)
    return skill_dir


@pytest.mark.asyncio
async def test_list_user_scope_finds_installed(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    skills = await store.list(scope="user", user_id="any")
    assert len(skills) == 1
    assert skills[0].manifest.name == "alpha"
    assert skills[0].body.strip() == "Body."
    assert skills[0].enabled is True


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(tmp_root):
    store = FilesystemSkillStore(root=tmp_root)
    assert await store.get("nope", scope="user", user_id="any") is None


@pytest.mark.asyncio
async def test_disabled_marker_flips_enabled(tmp_root, installed_alpha):
    (installed_alpha / ".disabled").touch()
    store = FilesystemSkillStore(root=tmp_root)
    skills = await store.list(scope="user", user_id="any")
    assert skills[0].enabled is False
