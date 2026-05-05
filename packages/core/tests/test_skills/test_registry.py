import pytest
from openlia.skills import (
    FilesystemSkillStore,
    LayeredSkillStore,
    SkillRegistry,
)

SECRETARY_SKILL = """---
name: greet-skill
description: Says hi.
version: "1.0.0"
departments: [secretary]
---
Body.
"""

GLOBAL_SKILL = """---
name: tone
description: Plain English voice.
version: "1.0.0"
departments: ["*"]
---
Body.
"""


@pytest.fixture
def populated_root(tmp_path):
    (tmp_path / "user" / "greet-skill").mkdir(parents=True)
    (tmp_path / "user" / "greet-skill" / "SKILL.md").write_text(SECRETARY_SKILL)
    (tmp_path / "system" / "tone").mkdir(parents=True)
    (tmp_path / "system" / "tone" / "SKILL.md").write_text(GLOBAL_SKILL)
    return tmp_path


@pytest.mark.asyncio
async def test_visible_for_secretary_user(populated_root):
    fs = FilesystemSkillStore(root=populated_root)
    layered = LayeredSkillStore(system=fs, user=fs)
    reg = SkillRegistry(store=layered)
    await reg.refresh(user_ids=["u1"])
    visible = reg.visible(department_id="secretary", user_id="u1")
    names = [s.manifest.name for s in visible]
    assert "greet-skill" in names
    assert "tone" in names


@pytest.mark.asyncio
async def test_filtered_by_department(populated_root):
    fs = FilesystemSkillStore(root=populated_root)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    visible = reg.visible(department_id="equity_research", user_id="u1")
    names = [s.manifest.name for s in visible]
    assert "greet-skill" not in names
    assert "tone" in names  # global


@pytest.mark.asyncio
async def test_disabled_skill_hidden(populated_root):
    (populated_root / "user" / "greet-skill" / ".disabled").touch()
    fs = FilesystemSkillStore(root=populated_root)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    names = [s.manifest.name for s in reg.visible(department_id="secretary", user_id="u1")]
    assert "greet-skill" not in names


@pytest.mark.asyncio
async def test_visible_excludes_session_disabled_ids(populated_root):
    """Per-session opt-out: chat input toggle hides skills for this turn
    even though the user has them installed and enabled in Settings."""
    fs = FilesystemSkillStore(root=populated_root)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    visible = reg.visible(
        department_id="secretary", user_id="u1", disabled_skill_ids=frozenset({"tone"})
    )
    names = [s.manifest.name for s in visible]
    assert "greet-skill" in names
    assert "tone" not in names


@pytest.mark.asyncio
async def test_get_returns_skill_for_user(populated_root):
    fs = FilesystemSkillStore(root=populated_root)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    assert reg.get("tone", user_id="u1").manifest.name == "tone"
    assert reg.get("greet-skill", user_id="u1").manifest.name == "greet-skill"
    assert reg.get("ghost", user_id="u1") is None
