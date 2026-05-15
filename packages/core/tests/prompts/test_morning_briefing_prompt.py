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
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        search_budget=5,
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
        current_date="2026-05-05",
        current_date_long="Tuesday, May 5, 2026",
        has_tools=False,
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
        current_date="2026-05-05",
        current_date_long="Tuesday, May 5, 2026",
        has_tools=False,
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
        current_date="2026-05-05",
        current_date_long="Tuesday, May 5, 2026",
        has_tools=False,
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
        current_date="2026-05-05",
        current_date_long="Tuesday, May 5, 2026",
        has_tools=False,
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
        current_date="2026-05-05",
        current_date_long="Tuesday, May 5, 2026",
        has_tools=False,
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
        current_date="2026-05-05",
        current_date_long="Tuesday, May 5, 2026",
        has_tools=False,
    )
    assert brief != long_
    assert "brief" in brief.lower()
    assert "long" in long_.lower() or "elaborative" in long_.lower()
