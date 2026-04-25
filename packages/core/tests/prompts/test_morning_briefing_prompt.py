from pathlib import Path

import pytest
from openlia.llm.runtime.prompts import PromptLoader


@pytest.fixture
def loader() -> PromptLoader:
    root = Path(__file__).resolve().parents[2] / "src" / "openlia" / "prompts"
    return PromptLoader(root=root)


def test_system_prompt_mentions_briefing_role(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.system",
        style_guide="x",
    )
    assert "briefing" in text.lower()
    assert "analyst" in text.lower()


def test_user_prompt_renders_enabled_sections(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        user_input="",
        length="standard",
        enabled_sections=["executive_summary", "global_macro"],
        section_topics={
            "global_macro": [
                {"topic": "War", "notes": "Russia-Ukraine"},
                {"topic": "Energy", "notes": ""},
            ],
        },
        custom_sections=[],
        reference_portfolio=None,
    )
    assert "executive_summary" in text
    assert "global_macro" in text
    assert "War" in text
    assert "Russia-Ukraine" in text
    assert "Energy" in text


def test_user_prompt_renders_custom_sections(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        user_input="",
        length="standard",
        enabled_sections=[],
        section_topics={},
        custom_sections=[
            {
                "id": "abc",
                "title": "My Macro Focus",
                "description": "Focus on EUR and JPY crosses.",
            },
        ],
        reference_portfolio=None,
    )
    assert "My Macro Focus" in text
    assert "EUR" in text or "JPY" in text


def test_user_prompt_includes_reference_portfolio_when_provided(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        user_input="",
        length="standard",
        enabled_sections=["upcoming_preview"],
        section_topics={},
        custom_sections=[],
        reference_portfolio=[
            {"ticker": "AAPL", "name": "Apple Inc."},
            {"ticker": "NVDA", "name": "NVIDIA"},
        ],
    )
    assert "AAPL" in text
    assert "NVDA" in text


def test_user_prompt_omits_reference_portfolio_when_none(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        user_input="",
        length="standard",
        enabled_sections=[],
        section_topics={},
        custom_sections=[],
        reference_portfolio=None,
    )
    assert "Reference portfolio" not in text


def test_length_knob_changes_prompt(loader: PromptLoader) -> None:
    brief = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        user_input="",
        length="brief",
        enabled_sections=[],
        section_topics={},
        custom_sections=[],
        reference_portfolio=None,
    )
    long_ = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        user_input="",
        length="long",
        enabled_sections=[],
        section_topics={},
        custom_sections=[],
        reference_portfolio=None,
    )
    assert brief != long_
    assert "brief" in brief.lower()
    assert "long" in long_.lower() or "elaborative" in long_.lower()
