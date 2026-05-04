from __future__ import annotations

import pytest
from openlia.llm.runtime.chat import build_chat_system_prompt
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

SAMPLE = """---
name: alpha
description: Alpha skill.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


@pytest.mark.asyncio
async def test_secretary_prompt_includes_alpha(tmp_path):
    (tmp_path / "user" / "alpha").mkdir(parents=True)
    (tmp_path / "user" / "alpha" / "SKILL.md").write_text(SAMPLE)
    fs = FilesystemSkillStore(root=tmp_path)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    prompt = build_chat_system_prompt(department_id="secretary", user_id="u1", registry=reg)
    assert "alpha" in prompt
    assert "Alpha skill." in prompt
