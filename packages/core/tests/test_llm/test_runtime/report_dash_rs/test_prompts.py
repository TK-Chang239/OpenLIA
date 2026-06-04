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
