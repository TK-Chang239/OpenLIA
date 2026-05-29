from openlia.llm.runtime.report_eu.prompts import build_system_prompt
from openlia.llm.runtime.report_eu.schemas import (
    EnabledConnectors,
    RunRequest,
    TriggerContext,
)
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


def _req(connectors: EnabledConnectors, trigger: TriggerContext | None) -> RunRequest:
    return RunRequest(
        subject="MSFT.US Q3 FY26 earnings",
        template=TemplateSpec(
            template_id="eu_default",
            name="Earnings Update",
            shape_description="Post-earnings scorecard",
            ticker_anchored=True,
            default_length="normal",
            sections=[SectionSpec(id="quick_take", title="Quick Take", intent="TLDR")],
        ),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=connectors,
        trigger_context=trigger,
    )


def test_prompt_includes_trigger_context():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(),
            TriggerContext(ticker="MSFT.US", fiscal_period="Q3 FY26", eps_estimate="2.50"),
        )
    )
    assert "Q3 FY26" in prompt
    assert "2.50" in prompt


def test_prompt_lists_available_connectors():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(financial=True, earnings_calendar=False, web_search=True),
            None,
        )
    )
    assert "get_fundamentals" in prompt or "financial data" in prompt.lower()
    assert "web search" in prompt.lower()


def test_prompt_states_no_tools_when_all_off():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(financial=False, earnings_calendar=False, web_search=False),
            None,
        )
    )
    assert "no data tools" in prompt.lower() or "without tools" in prompt.lower()


def test_prompt_lists_template_sections():
    prompt = build_system_prompt(_req(EnabledConnectors(), None))
    assert "quick_take" in prompt
