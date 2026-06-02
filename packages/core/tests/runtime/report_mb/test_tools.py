from openlia.llm.runtime.report_mb.ledger import CitationLedger
from openlia.llm.runtime.report_mb.schemas import EnabledConnectors
from openlia.llm.runtime.report_mb.tools import build_catalog
from openlia.llm.runtime.report_mb.tools.data_tools import build_data_tools
from openlia.llm.runtime.report_mb.transports import MbDataTransports
from openlia.llm.runtime.report_mb.workspace import RunWorkspace
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec


def _template() -> TemplateSpec:
    return TemplateSpec(
        template_id="mb_default",
        name="Morning Briefing",
        shape_description="Recurring market briefing",
        ticker_anchored=False,
        default_length="normal",
        sections=[SectionSpec(id="overnight", title="Overnight", intent="What moved")],
    )


def _transports() -> MbDataTransports:
    return MbDataTransports(
        quotes=lambda tickers: [{"ticker": t, "close": 1.0} for t in tickers],
        prices=lambda ticker, rng: [{"ticker": ticker, "range": rng}],
        news=lambda **kwargs: [{"title": "headline", "symbol": kwargs.get("symbol")}],
        economic_calendar=lambda window: [{"event": "CPI", "window": window}],
        macro_indicators=lambda keys: {k: 1.0 for k in keys},
    )


def _workspace(ledger: CitationLedger) -> RunWorkspace:
    return RunWorkspace(template=_template(), ledger=ledger, subject="Morning Briefing")


def test_catalog_with_eodhd_has_market_tools_not_earnings_calendar():
    ledger = CitationLedger()
    catalog = build_catalog(
        ledger=ledger,
        workspace=_workspace(ledger),
        transports=_transports(),
        enabled_connectors=EnabledConnectors(provider_ids=frozenset({"eodhd"})),
    )
    names = set(catalog.by_name())
    assert {
        "get_quotes",
        "get_historical_prices",
        "get_news",
        "get_economic_calendar",
        "get_macro_indicators",
        "write_section",
        "set_cover",
    } <= names
    assert "get_earnings_calendar" not in names
    assert "get_fundamentals" not in names


def test_catalog_without_eodhd_has_only_output_tools():
    ledger = CitationLedger()
    catalog = build_catalog(
        ledger=ledger,
        workspace=_workspace(ledger),
        transports=_transports(),
        enabled_connectors=EnabledConnectors(provider_ids=frozenset()),
    )
    names = set(catalog.by_name())
    assert "get_quotes" not in names
    assert {"write_section", "set_cover"} <= names


def test_web_search_absent_when_disabled():
    ledger = CitationLedger()
    catalog = build_catalog(
        ledger=ledger,
        workspace=_workspace(ledger),
        transports=_transports(),
        enabled_connectors=EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=False),
    )
    assert catalog.native_tools == ()
    assert "web_search" not in {d.name for d in catalog.descriptors}


def test_web_search_present_when_enabled():
    ledger = CitationLedger()
    catalog = build_catalog(
        ledger=ledger,
        workspace=_workspace(ledger),
        transports=_transports(),
        enabled_connectors=EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=True),
    )
    assert catalog.native_tools == ("web_search",)


def test_get_quotes_logs_to_ledger_and_echoes_source_id():
    ledger = CitationLedger()
    calls: list[list[str]] = []

    def quotes(tickers: list[str]) -> list[dict]:
        calls.append(tickers)
        return [{"ticker": t, "close": 10.0} for t in tickers]

    tools = build_data_tools(
        ledger=ledger,
        quotes=quotes,
        prices=lambda t, r: [],
        news=lambda **k: [],
        economic_calendar=lambda w: [],
        macro_indicators=lambda k: {},
    )
    tool = next(t for t in tools if t.descriptor.name == "get_quotes")
    result = tool.execute({"tickers": ["AAPL.US", "MSFT.US"]})

    assert calls == [["AAPL.US", "MSFT.US"]]
    source_id = result.payload["source_id"]
    assert source_id.startswith("eodhd")
    assert ledger.lookup(source_id) is not None
    assert "AAPL.US" in str(result.payload)


def test_get_economic_calendar_logs_to_ledger():
    ledger = CitationLedger()
    tools = build_data_tools(
        ledger=ledger,
        quotes=lambda t: [],
        prices=lambda t, r: [],
        news=lambda **k: [],
        economic_calendar=lambda window: [{"event": "CPI", "window": window}],
        macro_indicators=lambda k: {},
    )
    tool = next(t for t in tools if t.descriptor.name == "get_economic_calendar")
    result = tool.execute({"window": "this_week"})
    assert "CPI" in str(result.payload)
    assert ledger.lookup(result.payload["source_id"]) is not None


def test_get_news_market_wide_when_no_symbol():
    ledger = CitationLedger()
    seen: list = []

    def news(*, symbol=None, **_kwargs):
        seen.append(symbol)
        return [{"title": "Markets rally", "symbol": symbol}]

    tools = build_data_tools(
        ledger=ledger,
        quotes=lambda t: [],
        prices=lambda t, r: [],
        news=news,
        economic_calendar=lambda w: [],
        macro_indicators=lambda k: {},
    )
    tool = next(t for t in tools if t.descriptor.name == "get_news")
    tool.execute({})
    assert seen == [None]
