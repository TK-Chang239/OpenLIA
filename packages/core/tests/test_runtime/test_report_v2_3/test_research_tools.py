"""Unit tests for v2.3 research tool factories and ToolResult shape."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.research import (
    NullToolExecutor,
    ToolExecutionError,
    build_eodhd_tools,
    build_research_tools,
    build_web_search_tool,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    DataProviderSource,
    WebSource,
)

# ---------------------------------------------------------------------------
# build_eodhd_tools
# ---------------------------------------------------------------------------


def test_build_eodhd_tools_returns_three_tools() -> None:
    tools = build_eodhd_tools(
        fundamentals=lambda t: {"General": {"Code": t}},
        prices=lambda t, f, to: [{"date": f, "close": 100.0}],
        news=lambda t, n: [{"title": "x", "url": "u"}],
    )
    names = [t.name for t in tools]
    assert names == ["get_fundamentals", "get_historical_prices", "get_company_news"]


def test_fundamentals_tool_attaches_data_provider_provenance() -> None:
    tools = build_eodhd_tools(
        fundamentals=lambda t: {"General": {"Code": t}, "Highlights": {"Revenue": 100.0}},
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )
    fundamentals = next(t for t in tools if t.name == "get_fundamentals")
    result = fundamentals.execute({"ticker": "NVDA.US"})
    assert isinstance(result.provenance, DataProviderSource)
    assert result.provenance.provider == "EODHD"
    assert result.provenance.endpoint == "fundamentals"
    assert result.payload["General"]["Code"] == "NVDA.US"


def test_prices_tool_requires_dates() -> None:
    tools = build_eodhd_tools(
        fundamentals=lambda t: {},
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )
    prices = next(t for t in tools if t.name == "get_historical_prices")
    with pytest.raises(ToolExecutionError, match="from_date"):
        prices.execute({"ticker": "NVDA"})


def test_prices_tool_records_period_range() -> None:
    tools = build_eodhd_tools(
        fundamentals=lambda t: {},
        prices=lambda t, f, to: [{"date": f, "close": 1.0}, {"date": to, "close": 2.0}],
        news=lambda *a, **kw: [],
    )
    prices = next(t for t in tools if t.name == "get_historical_prices")
    out = prices.execute({"ticker": "NVDA", "from_date": "2025-01-01", "to_date": "2025-01-31"})
    assert isinstance(out.provenance, DataProviderSource)
    assert out.provenance.period == "2025-01-01..2025-01-31"
    assert len(out.payload["rows"]) == 2


def test_news_tool_caps_limit() -> None:
    captured = {}

    def news_transport(ticker: str, n: int) -> list:
        captured["n"] = n
        return [{"title": "h", "url": "u"} for _ in range(n)]

    tools = build_eodhd_tools(
        fundamentals=lambda t: {},
        prices=lambda *a, **kw: [],
        news=news_transport,
    )
    news = next(t for t in tools if t.name == "get_company_news")
    out = news.execute({"ticker": "NVDA", "limit": 99})
    assert captured["n"] == 20  # clamped to the schema's max
    assert len(out.payload["articles"]) == 20


def test_tool_wraps_upstream_error_as_tool_execution_error() -> None:
    def boom(_t: str) -> dict:
        raise ConnectionError("HTTP 500")

    tools = build_eodhd_tools(
        fundamentals=boom,
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )
    fundamentals = next(t for t in tools if t.name == "get_fundamentals")
    with pytest.raises(ToolExecutionError, match="HTTP 500"):
        fundamentals.execute({"ticker": "NVDA"})


def test_missing_ticker_raises_tool_execution_error() -> None:
    tools = build_eodhd_tools(
        fundamentals=lambda t: {},
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )
    for t in tools:
        with pytest.raises(ToolExecutionError, match="ticker"):
            t.execute({})


# ---------------------------------------------------------------------------
# build_web_search_tool
# ---------------------------------------------------------------------------


def test_web_search_tool_attaches_web_source_provenance() -> None:
    def transport(query: str, n: int) -> list:
        return [{"url": "https://x.test/a", "title": "A", "snippet": "..."}]

    tool = build_web_search_tool(transport)
    result = tool.execute({"query": "nvda revenue", "max_results": 1})
    assert isinstance(result.provenance, WebSource)
    assert result.payload["query"] == "nvda revenue"
    assert len(result.payload["results"]) == 1


def test_web_search_requires_query() -> None:
    tool = build_web_search_tool(lambda q, n: [])
    with pytest.raises(ToolExecutionError, match="query"):
        tool.execute({})


# ---------------------------------------------------------------------------
# build_research_tools
# ---------------------------------------------------------------------------


def test_build_research_tools_omits_web_search_when_not_provided() -> None:
    tools = build_research_tools(
        fundamentals=lambda t: {},
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )
    assert [t.name for t in tools] == [
        "get_fundamentals",
        "get_historical_prices",
        "get_company_news",
    ]


def test_build_research_tools_includes_web_search_when_provided() -> None:
    tools = build_research_tools(
        fundamentals=lambda t: {},
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
        web_search=lambda q, n: [],
    )
    assert tools[-1].name == "web_search"


# ---------------------------------------------------------------------------
# NullToolExecutor
# ---------------------------------------------------------------------------


def test_null_tool_executor_always_raises() -> None:
    null = NullToolExecutor("EODHD_API_KEY not set")
    with pytest.raises(ToolExecutionError, match="EODHD_API_KEY"):
        null("NVDA")
