"""Concrete research tools — EODHD wrappers + a web_search slot.

The factories here accept *transport callables* rather than the
``eodhd.APIClient`` instance itself. That keeps the core package free
of the SDK import (it lives in optional extras) and lets tests script
the data flow without monkey-patching.

The wiring layer (``services/v2_3_wiring.py``) instantiates the
EODHD client and binds its methods to the transport signatures
expected here.

Tool catalog (first cut — kept narrow on purpose; more land as helpers
graduate from v2.2):

  - ``get_fundamentals``: latest snapshot (general info + financials).
  - ``get_historical_prices``: OHLCV for a date range.
  - ``get_company_news``: recent headlines + URLs.
  - ``web_search``: optional, plugged in via callable.

Each tool's ``execute`` builds a v2.3 ``Provenance`` using the SDK
endpoint name and the moment of fetch, so any BundleFact derived from
the result inherits the correct source pedigree at the call site —
not stitched together later from sketchy heuristics.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..schemas import DataProviderSource, WebSource
from .tools import ResearchTool, ToolDescriptor, ToolExecutionError, ToolResult

# ---------------------------------------------------------------------------
# Transport signatures the wiring layer must satisfy
# ---------------------------------------------------------------------------

# A function the EODHD tools call to fetch fundamentals for a ticker.
# Returns the raw JSON dict from EODHD; the tool wraps it with provenance.
FundamentalsTransport = Callable[[str], dict[str, Any]]

# (ticker, from_date_iso, to_date_iso) -> list of OHLCV dicts.
PricesTransport = Callable[[str, str, str], list[dict[str, Any]]]

# (ticker, limit) -> list of news article dicts {title, url, date, ...}.
NewsTransport = Callable[[str, int], list[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Tool factories
# ---------------------------------------------------------------------------


def build_eodhd_tools(
    *,
    fundamentals: FundamentalsTransport,
    prices: PricesTransport,
    news: NewsTransport,
) -> list[ResearchTool]:
    """Return the three EODHD-backed tools bound to the given transports."""

    def _now() -> datetime:
        return datetime.now(UTC)

    def _fundamentals_exec(args: dict[str, Any]) -> ToolResult:
        ticker = _require_ticker(args)
        try:
            payload = fundamentals(ticker)
        except Exception as exc:
            raise ToolExecutionError(
                f"EODHD get_fundamentals failed for {ticker!r}: {exc}"
            ) from exc
        provenance = DataProviderSource(
            provider="EODHD",
            endpoint="fundamentals",
            period="latest",
            retrieved_at=_now(),
        )
        summary = f"Fundamentals snapshot for {ticker}."
        return ToolResult(payload=_ensure_dict(payload), provenance=provenance, summary=summary)

    def _prices_exec(args: dict[str, Any]) -> ToolResult:
        ticker = _require_ticker(args)
        from_date = str(args.get("from_date") or "").strip()
        to_date = str(args.get("to_date") or "").strip()
        if not from_date or not to_date:
            raise ToolExecutionError(
                "get_historical_prices requires `from_date` and `to_date` (YYYY-MM-DD)."
            )
        try:
            rows = prices(ticker, from_date, to_date)
        except Exception as exc:
            raise ToolExecutionError(
                f"EODHD get_historical_prices failed for {ticker!r}: {exc}"
            ) from exc
        provenance = DataProviderSource(
            provider="EODHD",
            endpoint="eod",
            period=f"{from_date}..{to_date}",
            retrieved_at=_now(),
        )
        summary = f"Historical OHLCV for {ticker} ({from_date} -> {to_date}): {len(rows)} rows."
        return ToolResult(
            payload={"rows": list(rows)},
            provenance=provenance,
            summary=summary,
        )

    def _news_exec(args: dict[str, Any]) -> ToolResult:
        ticker = _require_ticker(args)
        limit_raw = args.get("limit", 5)
        try:
            limit = max(1, min(20, int(limit_raw)))
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError(
                f"get_company_news: `limit` must be 1..20 (got {limit_raw!r})."
            ) from exc
        try:
            articles = news(ticker, limit)
        except Exception as exc:
            raise ToolExecutionError(
                f"EODHD get_company_news failed for {ticker!r}: {exc}"
            ) from exc
        provenance = DataProviderSource(
            provider="EODHD",
            endpoint="news",
            period="recent",
            retrieved_at=_now(),
        )
        summary = f"Recent news for {ticker}: {len(articles)} headlines."
        return ToolResult(
            payload={"articles": list(articles)},
            provenance=provenance,
            summary=summary,
        )

    return [
        ResearchTool(
            descriptor=ToolDescriptor(
                name="get_fundamentals",
                description=(
                    "Fetch the latest EODHD fundamentals snapshot for a ticker: "
                    "general info, latest income-statement, balance-sheet, "
                    "cash-flow figures. Use this when you need any reported "
                    "financial line item (revenue, margins, debt, shares, etc.). "
                    "For leverage, compute net cash / net debt from the "
                    "balance-sheet components — cash, short-term investments, "
                    "and total debt — and prefer that computed figure over "
                    "vendor aggregate fields like netDebt, which vary in what "
                    "they include; keep any figure you present reconciled with "
                    "the components you cite."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Equity ticker, EODHD-formatted (e.g. 'NVDA.US').",
                        },
                    },
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            execute=_fundamentals_exec,
        ),
        ResearchTool(
            descriptor=ToolDescriptor(
                name="get_historical_prices",
                description=(
                    "Fetch daily OHLCV bars from EODHD for a date range. Use "
                    "for price-action context, return calcs, drawdowns, or "
                    "plotting performance vs peers."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "from_date": {
                            "type": "string",
                            "description": "Inclusive ISO date YYYY-MM-DD.",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "Inclusive ISO date YYYY-MM-DD.",
                        },
                    },
                    "required": ["ticker", "from_date", "to_date"],
                    "additionalProperties": False,
                },
            ),
            execute=_prices_exec,
        ),
        ResearchTool(
            descriptor=ToolDescriptor(
                name="get_company_news",
                description=(
                    "Fetch recent company headlines from EODHD. Returns titles "
                    "and URLs. Use to surface catalysts, management changes, "
                    "or recent disclosures. Headlines are not statements of "
                    "fact — chase URLs with web_search if you need detail."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 5,
                        },
                    },
                    "required": ["ticker"],
                    "additionalProperties": False,
                },
            ),
            execute=_news_exec,
        ),
    ]


# A function the web_search tool calls. Signature: (query, max_results)
# -> list[{"url": str, "title": str|None, "snippet": str}].
WebSearchTransport = Callable[[str, int], list[dict[str, Any]]]


def build_web_search_tool(transport: WebSearchTransport) -> ResearchTool:
    """Return a single web_search tool bound to the given transport.

    The tool's ``execute`` is called once per LLM tool call and returns
    a list of results in its payload. Each web hit is *not* a fact yet
    — the model must read the snippets and decide which to convert into
    BundleFacts. When it does, it emits the result's URL/snippet so the
    researcher can attach a ``WebSource`` provenance.
    """

    def _exec(args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ToolExecutionError("web_search requires a non-empty `query`.")
        max_results = args.get("max_results", 5)
        try:
            count = max(1, min(10, int(max_results)))
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError(
                f"web_search: `max_results` must be 1..10 (got {max_results!r})."
            ) from exc
        try:
            results = transport(query, count)
        except Exception as exc:
            raise ToolExecutionError(f"web_search failed: {exc}") from exc

        # We attach a placeholder WebSource so the call carries provenance
        # for telemetry. Per-fact provenance is built by the researcher
        # from the specific URL the model cites.
        placeholder = WebSource(
            url="search://" + query,
            title=f"Search results for {query!r}",
            publisher=None,
            snippet=f"{len(results)} hit(s)",
            retrieved_at=datetime.now(UTC),
        )
        return ToolResult(
            payload={"query": query, "results": list(results)},
            provenance=placeholder,
            summary=f"Web search '{query}': {len(results)} hit(s).",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="web_search",
            description=(
                "Run a web search for narrative or recent context EODHD "
                "doesn't cover (regulatory news, product launches, mgmt "
                "commentary). Returns titles + URLs + snippets. Quote the "
                "URL and snippet verbatim when you turn a hit into a fact."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        execute=_exec,
    )


def build_research_tools(
    *,
    fundamentals: FundamentalsTransport,
    prices: PricesTransport,
    news: NewsTransport,
    web_search: WebSearchTransport | None = None,
) -> list[ResearchTool]:
    """Assemble the full v2.3 starter tool catalog."""
    tools = build_eodhd_tools(fundamentals=fundamentals, prices=prices, news=news)
    if web_search is not None:
        tools.append(build_web_search_tool(web_search))
    return tools


# ---------------------------------------------------------------------------
# Inert defaults — used when the wiring layer has no credentials
# ---------------------------------------------------------------------------


class NullToolExecutor:
    """Tool executor that always fails — used when no API keys are set.

    The factory hands one of these to ``build_research_tools`` so the
    LLM can still see the tool surface but is told upfront that calls
    will not succeed. This is preferable to omitting tools — the model
    learns the shape and the missing-credential message routes back as
    a clear failure rather than silent absence.
    """

    def __init__(self, message: str) -> None:
        self._message = message

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise ToolExecutionError(self._message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_ticker(args: dict[str, Any]) -> str:
    raw = args.get("ticker")
    if not isinstance(raw, str) or not raw.strip():
        raise ToolExecutionError("Argument `ticker` is required and must be a non-empty string.")
    return raw.strip()


def _ensure_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {"value": payload}
