from openlia.llm.runtime.report_eu.prompts import (
    ConnectorPromptInfo,
    build_system_prompt,
)
from openlia.llm.runtime.report_eu.schemas import (
    EnabledConnectors,
    RunRequest,
    TriggerContext,
)
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


def _req(
    connectors: EnabledConnectors,
    trigger: TriggerContext | None,
    instructions: str | None = None,
) -> RunRequest:
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
        instructions=instructions,
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
            EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=True),
            None,
        )
    )
    assert "get_fundamentals" in prompt or "financial data" in prompt.lower()
    assert "web search" in prompt.lower()


def test_prompt_states_no_tools_when_all_off():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(provider_ids=frozenset(), web_search=False),
            None,
        )
    )
    assert "no data tools" in prompt.lower() or "without tools" in prompt.lower()


def test_prompt_lists_connector_tools_alongside_eodhd():
    prompt = build_system_prompt(
        _req(
            EnabledConnectors(provider_ids=frozenset({"eodhd"})),
            None,
        ),
        connector_tools=(
            ConnectorPromptInfo(
                label="newsapi_ai",
                tools=(("newsapi_ai__search", "Search news"),),
            ),
        ),
    )
    assert "get_fundamentals" in prompt
    assert "newsapi_ai" in prompt
    assert "newsapi_ai__search" in prompt
    assert "Search news" in prompt


def test_prompt_no_connector_block_when_only_eodhd():
    prompt = build_system_prompt(_req(EnabledConnectors(provider_ids=frozenset({"eodhd"})), None))
    assert "get_fundamentals" in prompt
    assert "__" not in prompt
    assert "no data tools" not in prompt.lower()


def test_prompt_fallback_when_no_connectors_and_no_tools():
    prompt = build_system_prompt(
        _req(EnabledConnectors(provider_ids=frozenset(), web_search=False), None),
        connector_tools=(),
    )
    assert "no data tools" in prompt.lower()


def test_prompt_includes_earnings_data_priority_when_tools_available():
    prompt = build_system_prompt(_req(EnabledConnectors(provider_ids=frozenset({"eodhd"})), None))
    lowered = prompt.lower()
    assert "earnings call transcript" in lowered
    assert "beat/miss" in lowered
    assert "discovery interface" in lowered


def test_data_priority_directive_names_no_provider():
    prompt = build_system_prompt(
        _req(EnabledConnectors(provider_ids=frozenset({"eodhd"})), None),
        connector_tools=(
            ConnectorPromptInfo(
                label="alphavantage",
                tools=(("alphavantage__TOOL_LIST", "List tools"),),
            ),
        ),
    )
    # The directive is connector-agnostic: it must read the same whether or
    # not any specific provider is enabled. Isolate just the directive
    # paragraph and assert no provider label leaked into it.
    tail = prompt.split("Prioritize the data that defines")[1]
    directive = tail.split("primary reported data.")[0]
    assert "alphavantage" not in directive.lower()
    assert "eodhd" not in directive.lower()


def test_prompt_omits_data_priority_when_no_tools():
    prompt = build_system_prompt(
        _req(EnabledConnectors(provider_ids=frozenset(), web_search=False), None)
    )
    assert "discovery interface" not in prompt.lower()


def test_prompt_lists_template_sections():
    prompt = build_system_prompt(_req(EnabledConnectors(), None))
    assert "quick_take" in prompt


def test_prompt_includes_instructions_when_provided():
    prompt = build_system_prompt(
        _req(EnabledConnectors(), None, instructions="Favor FCF over EBITDA.")
    )
    assert "Analyst instructions" in prompt
    assert "Favor FCF over EBITDA." in prompt


def test_prompt_omits_instructions_when_absent():
    prompt = build_system_prompt(_req(EnabledConnectors(), None))
    assert "Analyst instructions" not in prompt
