from openlia.llm.runtime.report_eu import EuDataTransports
from openlia.llm.runtime.report_eu.ledger import CitationLedger
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors
from openlia.llm.runtime.report_eu.tools.registry import build_catalog
from openlia.llm.runtime.report_eu.workspace import RunWorkspace
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


def _workspace(ledger: CitationLedger) -> RunWorkspace:
    template = TemplateSpec(
        template_id="eu_default",
        name="EU",
        shape_description="scorecard",
        ticker_anchored=True,
        default_length="normal",
        sections=[SectionSpec(id="quick_take", title="Quick Take", intent="TLDR")],
    )
    return RunWorkspace(template=template, ledger=ledger, subject="MSFT.US")


def _transports() -> EuDataTransports:
    return EuDataTransports(
        fundamentals=lambda t: {},
        prices=lambda t, f, to: [],
        news=lambda t, limit: [],
        earnings_calendar=lambda t: [],
    )


def _catalog(connectors: EnabledConnectors):
    ledger = CitationLedger()
    return build_catalog(
        ledger=ledger,
        workspace=_workspace(ledger),
        transports=_transports(),
        enabled_connectors=connectors,
    )


def test_all_off_yields_output_tools_only():
    cat = _catalog(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    names = set(cat.by_name())
    assert {"write_section", "finalize"} <= names
    assert "get_fundamentals" not in names
    assert "get_earnings_calendar" not in names
    assert cat.native_tools == ()


def test_eodhd_on_adds_data_and_calendar_tools():
    cat = _catalog(EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=False))
    names = set(cat.by_name())
    assert {"get_fundamentals", "get_historical_prices", "get_company_news"} <= names
    assert "get_earnings_calendar" in names


def test_web_search_on_sets_native_tool():
    cat = _catalog(EnabledConnectors(provider_ids=frozenset(), web_search=True))
    assert cat.native_tools == ("web_search",)
