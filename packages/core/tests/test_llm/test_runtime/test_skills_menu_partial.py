from __future__ import annotations

from openlia.llm.runtime.prompts import PromptLoader


def test_menu_renders_when_skills_present() -> None:
    loader = PromptLoader()
    rendered = loader._env.get_template("shared/skills_menu.yaml.j2").render(
        skills_menu=[
            {"id": "alpha", "description": "Alpha skill.", "tools": []},
            {"id": "beta", "description": "Beta skill.", "tools": ["beta_tool"]},
        ]
    )
    assert "alpha" in rendered
    assert "Alpha skill." in rendered
    assert "beta_tool" in rendered


def test_menu_empty_when_no_skills() -> None:
    loader = PromptLoader()
    rendered = loader._env.get_template("shared/skills_menu.yaml.j2").render(skills_menu=[])
    assert rendered.strip() == ""
