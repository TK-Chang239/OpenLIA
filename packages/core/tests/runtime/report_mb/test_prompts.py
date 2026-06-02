from openlia.llm.runtime.report_mb.prompts import (
    ConnectorPromptInfo,
    build_system_prompt,
)
from openlia.llm.runtime.report_mb.schemas import (
    BriefingContext,
    EnabledConnectors,
    RunRequest,
)
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


def _req(
    connectors: EnabledConnectors,
    briefing: BriefingContext | None,
    instructions: str | None = None,
) -> RunRequest:
    return RunRequest(
        subject="Morning Briefing - 2026-06-02",
        template=TemplateSpec(
            template_id="mb_default",
            name="Morning Briefing",
            shape_description="Recurring market briefing",
            ticker_anchored=False,
            default_length="normal",
            sections=[SectionSpec(id="overnight", title="Overnight", intent="What moved")],
        ),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=connectors,
        briefing_context=briefing,
        instructions=instructions,
    )


def test_prompt_injects_briefing_context_and_instructions():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(),
            BriefingContext(run_date="2026-06-02", schedule_label="Pre-market briefing"),
            instructions="Lead with US index futures.",
        )
    )
    assert "2026-06-02" in prompt
    assert "Pre-market briefing" in prompt
    assert "US index futures" in prompt


def test_prompt_does_not_mention_earnings():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=True),
            BriefingContext(run_date="2026-06-02"),
        )
    )
    assert "earnings" not in prompt.lower()


def test_prompt_lists_market_data_tools_when_enabled():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=True),
            None,
        )
    )
    assert "get_quotes" in prompt or "market data" in prompt.lower()
    assert "web search" in prompt.lower()


def test_prompt_states_no_tools_when_all_off():
    prompt = build_system_prompt(
        _req(EnabledConnectors(provider_ids=frozenset(), web_search=False), None)
    )
    assert "no data tools" in prompt.lower()


def test_prompt_lists_template_sections():
    prompt = build_system_prompt(_req(EnabledConnectors(), None))
    assert "overnight" in prompt


def test_prompt_includes_instructions_block_when_provided():
    prompt = build_system_prompt(
        _req(EnabledConnectors(), None, instructions="Favor breadth over level.")
    )
    assert "Analyst instructions" in prompt
    assert "Favor breadth over level." in prompt


def test_prompt_omits_instructions_when_absent():
    prompt = build_system_prompt(_req(EnabledConnectors(), None))
    assert "Analyst instructions" not in prompt


def test_prompt_lists_connector_tools_alongside_market_data():
    prompt = build_system_prompt(
        _req(EnabledConnectors(provider_ids=frozenset({"eodhd"})), None),
        connector_tools=(
            ConnectorPromptInfo(
                label="newsapi_ai",
                tools=(("newsapi_ai__search", "Search news"),),
            ),
        ),
    )
    assert "newsapi_ai" in prompt
    assert "newsapi_ai__search" in prompt
