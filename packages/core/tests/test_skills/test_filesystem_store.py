import pytest
from openlia.skills import FilesystemSkillStore
from openlia.skills.parser import parse_skill_md

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


@pytest.mark.asyncio
async def test_install_writes_skill_md(tmp_root):
    store = FilesystemSkillStore(root=tmp_root)
    manifest, body = parse_skill_md(SAMPLE)
    installed = await store.install(
        source="folder", scope="user", user_id="u", body=body, manifest=manifest
    )
    assert installed.manifest.name == "alpha"
    assert (tmp_root / "user" / "alpha" / "SKILL.md").exists()


@pytest.mark.asyncio
async def test_install_rejects_duplicate(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    manifest, body = parse_skill_md(SAMPLE)
    with pytest.raises(FileExistsError):
        await store.install(
            source="folder", scope="user", user_id="u", body=body, manifest=manifest
        )


@pytest.mark.asyncio
async def test_uninstall_removes_directory(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    await store.uninstall("alpha", scope="user", user_id="u")
    assert not installed_alpha.exists()


@pytest.mark.asyncio
async def test_uninstall_missing_raises(tmp_root):
    store = FilesystemSkillStore(root=tmp_root)
    with pytest.raises(FileNotFoundError):
        await store.uninstall("ghost", scope="user", user_id="u")


@pytest.mark.asyncio
async def test_set_enabled_toggles_marker(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    await store.set_enabled("alpha", False, scope="user", user_id="u")
    assert (installed_alpha / ".disabled").exists()
    await store.set_enabled("alpha", True, scope="user", user_id="u")
    assert not (installed_alpha / ".disabled").exists()
