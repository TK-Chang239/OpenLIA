"""Earnings Update prompt renders expected content and branches on length."""

from __future__ import annotations

import pytest

from openlia.llm.runtime.prompts import PromptLoader


@pytest.fixture
def loader() -> PromptLoader:
    return PromptLoader()


def _ctx(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "user_input": "Analyze the latest Apple earnings release for AAPL.",
        "enabled_sections": ["quick_take", "key_financials"],
        "custom_sections": [],
        "length": "normal",
        "framework": {"id": "earnings_update", "sections": []},
    }
    base.update(overrides)
    return base


def test_system_prompt_mentions_department_role(loader: PromptLoader) -> None:
    text = loader.render("earnings_update", "report.system", style_guide="x")
    assert "earnings" in text.lower()
    assert "analyst" in text.lower()


def test_user_prompt_embeds_ticker_and_user_input(loader: PromptLoader) -> None:
    text = loader.render(
        "earnings_update",
        "report.earnings_update.user",
        **_ctx(user_input="Analyze the latest Apple earnings release for AAPL."),
    )
    assert "AAPL" in text
    assert "Apple" in text or "latest" in text


def test_length_knob_changes_prompt(loader: PromptLoader) -> None:
    concise = loader.render(
        "earnings_update",
        "report.earnings_update.user",
        **_ctx(length="concise"),
    )
    elaborative = loader.render(
        "earnings_update",
        "report.earnings_update.user",
        **_ctx(length="elaborative"),
    )
    assert concise != elaborative
    assert "concise" in concise.lower()
    assert "elaborative" in elaborative.lower() or "expansive" in elaborative.lower()
