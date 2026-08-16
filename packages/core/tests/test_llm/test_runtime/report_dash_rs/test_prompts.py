"""Tests for report_dash_rs prompt builder."""

from openlia.llm.runtime.report_dash_rs.prompts import (
    DASHBOARD_PROMPT_SPECS,
    build_system_prompt,
)
from openlia.llm.runtime.report_dash_rs.schemas import EnabledConnectors, RunRequest


def test_retail_sentiment_prompt_spec_present():
    spec = DASHBOARD_PROMPT_SPECS["retail_sentiment"]
    assert spec.workflow and spec.payload_shape


def test_build_system_prompt_mentions_web_search_and_ticker():
    req = RunRequest(
        dashboard_slug="retail_sentiment",
        subject="AAPL",
        provider_kind="anthropic",
        model="claude-sonnet-4-5",
        enabled_connectors=EnabledConnectors(provider_ids=frozenset(), web_search=True),
    )
    text = build_system_prompt(req)
    assert "AAPL" in text
    assert "web" in text.lower()


def test_prompt_omits_phantom_eodhd_tools_and_names_real_catalog():
    """Regression: the prompt must advertise only tools the catalog registers.

    RS deliberately omits the curated EODHD branch, so the prompt must not name
    the five EODHD tools it used to; it must name the real core tools instead.
    Enabling the ``eodhd`` provider_id used to trigger the phantom block.
    """
    req = RunRequest(
        dashboard_slug="retail_sentiment",
        subject="AAPL",
        provider_kind="anthropic",
        model="claude-sonnet-4-5",
        enabled_connectors=EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=True),
    )
    text = build_system_prompt(req)
    for phantom in (
        "get_quotes",
        "get_historical_prices",
        "get_news",
        "get_economic_calendar",
        "get_macro_indicators",
    ):
        assert phantom not in text, f"prompt still advertises phantom tool {phantom!r}"
    assert "classify_retail_sentiment" in text
    assert "emit_dashboard" in text
