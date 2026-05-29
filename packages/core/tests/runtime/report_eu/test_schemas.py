from openlia.llm.runtime.report_eu.schemas import (
    EnabledConnectors,
    RunRequest,
    TriggerContext,
)
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


def _template() -> TemplateSpec:
    return TemplateSpec(
        template_id="eu_default",
        name="Earnings Update",
        shape_description="Post-earnings scorecard",
        ticker_anchored=True,
        default_length="normal",
        sections=[SectionSpec(id="quick_take", title="Quick Take", intent="TLDR")],
    )


def test_enabled_connectors_defaults():
    c = EnabledConnectors()
    assert c.financial is True
    assert c.earnings_calendar is True
    assert c.web_search is False


def test_trigger_context_minimal():
    t = TriggerContext(ticker="MSFT.US")
    assert t.ticker == "MSFT.US"
    assert t.eps_estimate is None


def test_run_request_carries_connectors_and_trigger():
    req = RunRequest(
        subject="MSFT.US Q3 FY26 earnings",
        template=_template(),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=EnabledConnectors(web_search=True),
        trigger_context=TriggerContext(ticker="MSFT.US", fiscal_period="Q3 FY26"),
    )
    assert req.enabled_connectors.web_search is True
    assert req.trigger_context.fiscal_period == "Q3 FY26"
