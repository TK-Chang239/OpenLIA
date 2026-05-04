# packages/core/tests/test_llm/test_runtime/test_skills_menu_in_dept_prompts.py
import pytest
from openlia.llm.runtime.prompts import PromptLoader

CHAT_DEPTS = ["secretary"]  # Plan 1 wires Secretary's chat slot; reports below.


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_chat_system_renders_with_no_skills(dept):
    loader = PromptLoader()
    rendered = loader.render(dept, "chat.system", skills_menu=[])
    assert "Skills available" not in rendered  # empty branch


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_chat_system_renders_with_skills(dept):
    loader = PromptLoader()
    rendered = loader.render(
        dept,
        "chat.system",
        skills_menu=[{"id": "alpha", "description": "X.", "tools": []}],
    )
    assert "Skills available" in rendered
    assert "alpha" in rendered


def test_existing_render_calls_still_work_without_skills_menu():
    loader = PromptLoader()
    # No skills_menu kwarg — must not raise StrictUndefined.
    rendered = loader.render("secretary", "chat.system")
    assert isinstance(rendered, str)
