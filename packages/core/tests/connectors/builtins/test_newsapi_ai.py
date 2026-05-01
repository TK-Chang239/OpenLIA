"""Built-in NewsAPI.ai template tests."""

from __future__ import annotations

from openlia.connectors.builtins.newsapi_ai import NEWSAPI_AI_TEMPLATE
from openlia.connectors.types import Category


def test_newsapi_ai_template_id_and_category() -> None:
    assert NEWSAPI_AI_TEMPLATE.template_id == "newsapi_ai"
    assert NEWSAPI_AI_TEMPLATE.category == Category.NEWS
    assert NEWSAPI_AI_TEMPLATE.api_key_env_var == "NEWSAPI_AI_API_KEY"


def test_newsapi_ai_has_at_least_one_mode() -> None:
    assert len(NEWSAPI_AI_TEMPLATE.available_modes) >= 1


def test_newsapi_ai_runner_specs_cover_geopolitical_news() -> None:
    need_ids = {spec.need_id for spec in NEWSAPI_AI_TEMPLATE.runner_specs}
    assert "geopolitical_news" in need_ids


def test_newsapi_ai_canary_tool_set() -> None:
    assert NEWSAPI_AI_TEMPLATE.canary_tool is not None
