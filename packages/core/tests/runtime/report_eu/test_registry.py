from typing import Any

from openlia.llm.runtime.report_eu import EuDataTransports
from openlia.llm.runtime.report_eu.ledger import CitationLedger
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors
from openlia.llm.runtime.report_eu.tools.registry import build_catalog
from openlia.llm.runtime.report_eu.workspace import RunWorkspace
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


class FakeDispatcher:
    def __init__(self, tools: list[dict[str, Any]]) -> None:
        self._tools = tools

    def candidate_tools(self) -> list[dict[str, Any]]:
        return self._tools

    async def dispatch_tool_use(self, name: str, args: dict[str, Any]) -> Any:
        return {}


def _dispatcher_tool(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": "d",
        "input_schema": {"type": "object", "properties": {}},
    }


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


def _catalog(connectors: EnabledConnectors, dispatcher: Any = None):
    ledger = CitationLedger()
    return build_catalog(
        ledger=ledger,
        workspace=_workspace(ledger),
        transports=_transports(),
        enabled_connectors=connectors,
        dispatcher=dispatcher,
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


def test_hybrid_catalog_curated_eodhd_plus_dispatcher_connectors():
    dispatcher = FakeDispatcher([_dispatcher_tool("newsapi_ai__search")])
    cat = _catalog(
        EnabledConnectors(provider_ids=frozenset({"eodhd", "newsapi_ai"}), web_search=True),
        dispatcher=dispatcher,
    )
    names = set(cat.by_name())
    assert {"get_fundamentals", "get_historical_prices", "get_company_news"} <= names
    assert "get_earnings_calendar" in names
    assert "newsapi_ai__search" in names
    assert cat.native_tools == ("web_search",)
    descriptor_names = {d.name for d in cat.descriptors}
    assert "newsapi_ai__search" in descriptor_names


def test_dispatcher_only_no_eodhd_curated():
    dispatcher = FakeDispatcher([_dispatcher_tool("newsapi_ai__search")])
    cat = _catalog(
        EnabledConnectors(provider_ids=frozenset({"newsapi_ai"})),
        dispatcher=dispatcher,
    )
    names = set(cat.by_name())
    assert "get_fundamentals" not in names
    assert "get_earnings_calendar" not in names
    assert "newsapi_ai__search" in names


def test_dispatcher_none_is_curated_only():
    cat = _catalog(
        EnabledConnectors(provider_ids=frozenset({"eodhd"})),
        dispatcher=None,
    )
    names = set(cat.by_name())
    assert "get_fundamentals" in names
    assert not any("__" in n for n in names)
