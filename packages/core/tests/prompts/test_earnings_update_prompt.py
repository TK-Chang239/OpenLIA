"""Earnings Update prompt renders expected content and branches on length."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.prompts import PromptLoader


@pytest.fixture
def loader() -> PromptLoader:
    return PromptLoader()


def _ctx(**overrides: object) -> dict[str, object]:
    # `length` follows the `ReportRequest.length` contract: brief/standard/long.
    # `eu_runner` maps the user-facing config value (concise/normal/elaborative)
    # into one of these at the service call-site.
    base: dict[str, object] = {
        "user_input": "Analyze the latest Apple earnings release for AAPL.",
        "enabled_sections": ["quick_take", "key_financials"],
        "custom_sections": [],
        "length": "standard",
        "framework": {"id": "earnings_update", "sections": []},
    }
    base.update(overrides)
    return base


def test_system_prompt_mentions_department_role(loader: PromptLoader) -> None:
    text = loader.render(
        "earnings_update",
        "report.system",
        style_guide="x",
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        search_budget=5,
    )
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


def test_length_brief_selects_tight_branch(loader: PromptLoader) -> None:
    text = loader.render(
        "earnings_update",
        "report.earnings_update.user",
        **_ctx(length="brief"),
    )
    assert "LENGTH: BRIEF" in text
    assert "LENGTH: STANDARD" not in text
    assert "LENGTH: LONG" not in text


def test_length_standard_selects_balanced_branch(loader: PromptLoader) -> None:
    text = loader.render(
        "earnings_update",
        "report.earnings_update.user",
        **_ctx(length="standard"),
    )
    assert "LENGTH: STANDARD" in text
    assert "LENGTH: BRIEF" not in text
    assert "LENGTH: LONG" not in text


def test_length_long_selects_deep_branch(loader: PromptLoader) -> None:
    text = loader.render(
        "earnings_update",
        "report.earnings_update.user",
        **_ctx(length="long"),
    )
    assert "LENGTH: LONG" in text
    assert "LENGTH: BRIEF" not in text
    assert "LENGTH: STANDARD" not in text


def test_length_branches_produce_distinct_prompts(loader: PromptLoader) -> None:
    brief = loader.render("earnings_update", "report.earnings_update.user", **_ctx(length="brief"))
    long_ = loader.render("earnings_update", "report.earnings_update.user", **_ctx(length="long"))
    assert brief != long_
