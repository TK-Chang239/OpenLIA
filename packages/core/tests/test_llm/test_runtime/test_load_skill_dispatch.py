import pytest
from openlia.llm.runtime.tools import dispatch_load_skill
from openlia.skills import (
    FilesystemSkillStore,
    LayeredSkillStore,
    SkillRegistry,
)

SAMPLE = """---
name: alpha
description: A.
version: "1.0.0"
departments: [secretary]
---

Skill body content.
"""


@pytest.mark.asyncio
async def test_dispatch_returns_body(tmp_path):
    (tmp_path / "user" / "alpha").mkdir(parents=True)
    (tmp_path / "user" / "alpha" / "SKILL.md").write_text(SAMPLE)
    fs = FilesystemSkillStore(root=tmp_path)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    result = await dispatch_load_skill(reg, user_id="u1", skill_id="alpha", call_id="c1")
    assert result.ok
    assert "Skill body content" in result.payload["body"]


@pytest.mark.asyncio
async def test_dispatch_unknown_skill_returns_error(tmp_path):
    fs = FilesystemSkillStore(root=tmp_path)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    result = await dispatch_load_skill(reg, user_id="u1", skill_id="ghost", call_id="c1")
    assert not result.ok
    assert "ghost" in result.summary
