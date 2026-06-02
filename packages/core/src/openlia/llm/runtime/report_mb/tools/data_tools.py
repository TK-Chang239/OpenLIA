"""Market-data tools — curated EODHD tools for the Morning Briefing catalog.

The Morning Briefing engine writes a recurring market briefing rather
than a single-ticker earnings report, so its curated tools are
market-wide: multi-ticker quotes, historical prices, market or symbol
news, the economic calendar, and macro indicators. Each tool is backed
by an ``MbDataTransports`` callable supplied by the wiring layer, so the
core package stays free of the EODHD SDK.

Every successful tool call appends one entry to the run's
``CitationLedger`` and the returned payload begins with the assigned
``source_id`` (e.g. ``eodhd_3``) so the model knows what to cite. When a
transport raises, the wrapper surfaces a structured ``ToolExecutionError``
the model can read and react to instead of crashing the loop.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
    prune_empty,
)
from ...report_v2_3.schemas import DataProviderSource
from ..ledger import CitationLedger

# Transport signatures the Morning Briefing data tools dispatch against.
# (list of tickers) -> list of quote dicts.
QuotesTransport = Callable[[list[str]], list[dict[str, Any]]]
# (ticker, range token) -> list of OHLCV dicts.
PricesTransport = Callable[[str, str], list[dict[str, Any]]]
# (optional symbol keyword) -> list of news dicts; market-wide when omitted.
NewsTransport = Callable[..., list[dict[str, Any]]]
# (window token) -> list of economic-event dicts.
EconomicCalendarTransport = Callable[[str], list[dict[str, Any]]]
# (list of indicator keys) -> dict of indicator readings.
MacroIndicatorsTransport = Callable[[list[str]], dict[str, Any]]


def build_data_tools(
    *,
    ledger: CitationLedger,
    quotes: QuotesTransport,
    prices: PricesTransport,
    news: NewsTransport,
    economic_calendar: EconomicCalendarTransport,
    macro_indicators: MacroIndicatorsTransport,
) -> list[ResearchTool]:
    """Return the five curated Morning Briefing market tools, ledger-aware.

    Each tool dispatches against the matching ``MbDataTransports``
    callable, lands one ledger entry per successful call, and echoes the
    assigned ``source_id`` back in the tool result so the model can cite
    it.
    """
    return [
        _build_quotes_tool(ledger=ledger, quotes=quotes),
        _build_prices_tool(ledger=ledger, prices=prices),
        _build_news_tool(ledger=ledger, news=news),
        _build_economic_calendar_tool(ledger=ledger, economic_calendar=economic_calendar),
        _build_macro_indicators_tool(ledger=ledger, macro_indicators=macro_indicators),
    ]


def _build_quotes_tool(*, ledger: CitationLedger, quotes: QuotesTransport) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        tickers = _require_ticker_list(args, tool="get_quotes")
        try:
            rows = quotes(tickers)
        except Exception as exc:
            raise ToolExecutionError(f"get_quotes failed for {tickers!r}: {exc!s}") from exc
        provenance = _provenance("real-time/quotes", period="latest")
        summary = f"Latest quotes for {len(tickers)} ticker(s)."
        entry = ledger.append(
            tool_name="get_quotes",
            arguments=dict(args),
            result_summary=summary,
            provenance=_provenance_to_dict(provenance),
        )
        payload = {
            "source_id": entry.source_id,
            "summary": summary,
            "data": {"tickers": tickers, "quotes": prune_empty(list(rows))},
        }
        return ToolResult(payload=payload, provenance=provenance, summary=summary)

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="get_quotes",
            description=(
                "Fetch the latest quote for one or more tickers (price, change, "
                "volume). Use to read where the major indices, sectors, and "
                "names you cover are trading right now."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "EODHD-formatted tickers (e.g. ['SPY.US', 'QQQ.US']).",
                    },
                },
                "required": ["tickers"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def _build_prices_tool(*, ledger: CitationLedger, prices: PricesTransport) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        ticker = _require_ticker(args, tool="get_historical_prices")
        rng = str(args.get("range") or "").strip()
        if not rng:
            raise ToolExecutionError("get_historical_prices requires `range` (e.g. '1mo', '1y').")
        try:
            rows = prices(ticker, rng)
        except Exception as exc:
            raise ToolExecutionError(
                f"get_historical_prices failed for {ticker!r}: {exc!s}"
            ) from exc
        provenance = _provenance("eod", period=rng)
        summary = f"Historical prices for {ticker} ({rng}): {len(rows)} rows."
        entry = ledger.append(
            tool_name="get_historical_prices",
            arguments=dict(args),
            result_summary=summary,
            provenance=_provenance_to_dict(provenance),
        )
        payload = {
            "source_id": entry.source_id,
            "summary": summary,
            "data": {"ticker": ticker, "range": rng, "rows": prune_empty(list(rows))},
        }
        return ToolResult(payload=payload, provenance=provenance, summary=summary)

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="get_historical_prices",
            description=(
                "Fetch daily OHLCV bars for a ticker over a range token "
                "(e.g. '1mo', '3mo', '1y'). Use for trend, return, and "
                "drawdown context or to plot performance."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "range": {
                        "type": "string",
                        "description": "Range token, e.g. '1mo', '3mo', '6mo', '1y'.",
                    },
                },
                "required": ["ticker", "range"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def _build_news_tool(*, ledger: CitationLedger, news: NewsTransport) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        symbol_raw = args.get("symbol")
        symbol = (
            str(symbol_raw).strip() if isinstance(symbol_raw, str) and symbol_raw.strip() else None
        )
        try:
            articles = news(symbol=symbol)
        except Exception as exc:
            scope = symbol or "the market"
            raise ToolExecutionError(f"get_news failed for {scope}: {exc!s}") from exc
        provenance = _provenance("news", period="recent")
        scope = symbol or "market-wide"
        summary = f"Recent news ({scope}): {len(articles)} headline(s)."
        entry = ledger.append(
            tool_name="get_news",
            arguments=dict(args),
            result_summary=summary,
            provenance=_provenance_to_dict(provenance),
        )
        payload = {
            "source_id": entry.source_id,
            "summary": summary,
            "data": {"symbol": symbol, "articles": prune_empty(list(articles))},
        }
        return ToolResult(payload=payload, provenance=provenance, summary=summary)

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="get_news",
            description=(
                "Fetch recent news headlines. Omit `symbol` for market-wide "
                "headlines, or pass a ticker for company-specific news. Use "
                "to surface overnight catalysts and the day's drivers."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Optional ticker; omit for market-wide news.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def _build_economic_calendar_tool(
    *, ledger: CitationLedger, economic_calendar: EconomicCalendarTransport
) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        window = str(args.get("window") or "").strip()
        if not window:
            raise ToolExecutionError(
                "get_economic_calendar requires `window` (e.g. 'today', 'this_week')."
            )
        try:
            events = economic_calendar(window)
        except Exception as exc:
            raise ToolExecutionError(
                f"get_economic_calendar failed for window {window!r}: {exc!s}"
            ) from exc
        provenance = _provenance("calendar/economic", period=window)
        summary = f"Economic calendar ({window}): {len(events)} event(s)."
        entry = ledger.append(
            tool_name="get_economic_calendar",
            arguments=dict(args),
            result_summary=summary,
            provenance=_provenance_to_dict(provenance),
        )
        payload = {
            "source_id": entry.source_id,
            "summary": summary,
            "data": {"window": window, "events": prune_empty(list(events))},
        }
        return ToolResult(payload=payload, provenance=provenance, summary=summary)

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="get_economic_calendar",
            description=(
                "Fetch the economic calendar for a window (e.g. 'today', "
                "'this_week'): scheduled data releases and central-bank events "
                "with consensus where available. Use to flag the day's macro "
                "catalysts."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "Window token, e.g. 'today', 'this_week'.",
                    },
                },
                "required": ["window"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def _build_macro_indicators_tool(
    *, ledger: CitationLedger, macro_indicators: MacroIndicatorsTransport
) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        keys = _require_key_list(args)
        try:
            readings = macro_indicators(keys)
        except Exception as exc:
            raise ToolExecutionError(f"get_macro_indicators failed for {keys!r}: {exc!s}") from exc
        provenance = _provenance("macro-indicators", period="latest")
        summary = f"Macro indicators for {len(keys)} key(s)."
        entry = ledger.append(
            tool_name="get_macro_indicators",
            arguments=dict(args),
            result_summary=summary,
            provenance=_provenance_to_dict(provenance),
        )
        payload = {
            "source_id": entry.source_id,
            "summary": summary,
            "data": {"keys": keys, "indicators": prune_empty(_ensure_dict(readings))},
        }
        return ToolResult(payload=payload, provenance=provenance, summary=summary)

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="get_macro_indicators",
            description=(
                "Fetch current readings for macro indicators by key (e.g. "
                "'us_10y', 'vix', 'dxy', 'wti'). Use for the rates, "
                "volatility, dollar, and commodity backdrop."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Indicator keys, e.g. ['us_10y', 'vix', 'dxy'].",
                    },
                },
                "required": ["keys"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def _provenance(endpoint: str, *, period: str) -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint=endpoint,
        period=period,
        retrieved_at=datetime.now(UTC),
    )


def _require_ticker(args: dict[str, Any], *, tool: str) -> str:
    raw = args.get("ticker")
    if not isinstance(raw, str) or not raw.strip():
        raise ToolExecutionError(f"{tool} requires a non-empty `ticker`.")
    return raw.strip()


def _require_ticker_list(args: dict[str, Any], *, tool: str) -> list[str]:
    raw = args.get("tickers")
    if not isinstance(raw, list) or not raw:
        raise ToolExecutionError(f"{tool} requires a non-empty `tickers` list.")
    tickers = [str(t).strip() for t in raw if str(t).strip()]
    if not tickers:
        raise ToolExecutionError(f"{tool} requires at least one non-empty ticker.")
    return tickers


def _require_key_list(args: dict[str, Any]) -> list[str]:
    raw = args.get("keys")
    if not isinstance(raw, list) or not raw:
        raise ToolExecutionError("get_macro_indicators requires a non-empty `keys` list.")
    keys = [str(k).strip() for k in raw if str(k).strip()]
    if not keys:
        raise ToolExecutionError("get_macro_indicators requires at least one non-empty key.")
    return keys


def _ensure_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def _provenance_to_dict(provenance: Any) -> dict[str, Any]:
    """Best-effort serialization of a v2.3 Provenance variant."""
    if hasattr(provenance, "model_dump"):
        try:
            return provenance.model_dump(mode="json")
        except Exception:
            pass
    return {"raw": str(provenance)}
