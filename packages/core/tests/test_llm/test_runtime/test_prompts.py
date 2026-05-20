from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from openlia.llm.runtime.prompts import (
    PromptLoader,
    PromptSlotNotFound,
)


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / "prompts"
    shared = pdir / "shared"
    shared.mkdir(parents=True)
    (shared / "voice.yaml.j2").write_text("Speak concisely.\n")
    (shared / "output_discipline.yaml.j2").write_text("Return only the required format.")

    (pdir / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: |
                You are the Secretary.
                {% include "shared/voice.yaml.j2" %}
              welcome: |
                Hello {{ user_name | default('friend') }}.
            """
        )
    )

    (pdir / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Follow this style guide:
                {{ style_guide }}
                {% include "shared/output_discipline.yaml.j2" %}
              stock_initiation:
                user: |
                  Initiate {{ user_input }}.
                  Length: {{ length }}
                  Sections: {{ enabled_sections | join(', ') }}
            """
        )
    )
    return pdir


def test_render_simple_slot(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("secretary", "chat.welcome", user_name="Ada")
    assert "Hello Ada." in out


def test_render_simple_slot_with_default_context(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("secretary", "chat.welcome")
    assert "Hello friend." in out


def test_render_supports_shared_includes(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("secretary", "chat.system")
    assert "Secretary" in out
    assert "Speak concisely." in out


def test_render_nested_slot_with_context(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    out = loader.render(
        "equity_research",
        "report.stock_initiation.user",
        user_input="AAPL",
        length="standard",
        enabled_sections=["overview", "thesis"],
    )
    assert "Initiate AAPL." in out
    assert "overview, thesis" in out


def test_missing_slot_raises_prompt_slot_not_found(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    with pytest.raises(PromptSlotNotFound) as excinfo:
        loader.render("secretary", "chat.nope")
    assert "secretary" in str(excinfo.value)
    assert "chat.nope" in str(excinfo.value)


def test_missing_department_raises_prompt_slot_not_found(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    with pytest.raises(PromptSlotNotFound):
        loader.render("made_up", "chat.system")


def test_validate_department_slots_passes_when_all_declared(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    loader.validate_department_slots("secretary", expected=["chat.system", "chat.welcome"])


def test_validate_department_slots_raises_on_missing(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    with pytest.raises(PromptSlotNotFound, match=r"chat\.nope"):
        loader.validate_department_slots("secretary", expected=["chat.system", "chat.nope"])


def test_loader_caches_yaml_parse(prompts_dir: Path, monkeypatch) -> None:
    loader = PromptLoader(root=prompts_dir)
    loader.render("secretary", "chat.welcome", user_name="A")

    # Corrupt the file on disk; cached render should still succeed.
    (prompts_dir / "secretary.yaml").write_text("not: valid: yaml: at all")
    out = loader.render("secretary", "chat.welcome", user_name="B")
    assert "Hello B." in out


def test_rendered_string_is_jinja2_safe_for_json_values(prompts_dir: Path) -> None:
    loader = PromptLoader(root=prompts_dir)
    (prompts_dir / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              data:
                user: |
                  {{ blob | tojson }}
            """
        )
    )
    # Force cache invalidation by constructing a fresh loader.
    loader = PromptLoader(root=prompts_dir)
    out = loader.render("equity_research", "report.data.user", blob={"k": "v"})
    assert '{"k": "v"}' in out


def test_real_prompts_render_traditional_chinese_language_directive() -> None:
    """Renders equity_research.report.system with language='zh-TW' using
    the real shipped prompt root + shared/output_language.yaml.j2 partial.
    Confirms the directive lands in the assembled system prompt."""
    loader = PromptLoader()
    out = loader.render(
        "equity_research",
        "report.system",
        style_guide="neutral institutional tone",
        skills_menu=[],
        available_category_hints=[],
        current_date="2026-05-19",
        current_date_long="Tuesday, May 19, 2026",
        search_budget=4,
        connector_quirks=[],
        language="zh-TW",
    )
    assert "OUTPUT LANGUAGE" in out or "Output language" in out
    assert "繁體中文" in out


def test_real_prompts_omit_language_directive_when_english_default() -> None:
    loader = PromptLoader()
    out = loader.render(
        "equity_research",
        "report.system",
        style_guide="neutral institutional tone",
        skills_menu=[],
        available_category_hints=[],
        current_date="2026-05-19",
        current_date_long="Tuesday, May 19, 2026",
        search_budget=4,
        connector_quirks=[],
    )
    assert "繁體中文" not in out
