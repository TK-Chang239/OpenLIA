"""W1: hard-coded baseline fetches per report type."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest


class ToolDispatcher(Protocol):
    async def dispatch(self, provider: str, tool: str, args: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class BaselineCall:
    provider: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)

    def identifier(self) -> str:
        # EODHD exposes the ticker under different keys depending on the
        # tool (`ticker`, `symbol`, `symbols`, `code`, `s`). Check all of
        # them so the manifest identifier carries the ticker suffix and
        # downstream fact extractors can scope payloads by symbol.
        ticker = (
            self.args.get("ticker")
            or self.args.get("symbol")
            or self.args.get("symbols")
            or self.args.get("code")
            or self.args.get("s")
            or self.args.get("query")
            or ""
        )
        return f"{self.tool}/{ticker}" if ticker else self.tool


# Tool names + arg keys are matched against the EODHD connector's actual
# cached_tools (see DB connectors row). Income statement / balance sheet /
# cash flow / holders are not separate endpoints — that data ships inside
# get_fundamentals_data, so they're not requested here.
BASELINE_STOCK_INITIATION: tuple[BaselineCall, ...] = (
    BaselineCall("eodhd", "get_fundamentals_data", {"ticker": "{ticker}.US"}),
    BaselineCall("eodhd", "get_live_stock_prices", {"ticker": "{ticker}.US"}),
    BaselineCall("eodhd", "get_historical_market_capitalization_data", {"ticker": "{ticker}.US"}),
    BaselineCall("eodhd", "get_eod_historical_stock_market_data", {"symbol": "{ticker}.US"}),
    BaselineCall("eodhd", "get_earning_trends_data", {"symbols": "{ticker}.US"}),
    BaselineCall("eodhd", "get_insider_transactions_data", {"code": "{ticker}"}),
    BaselineCall("eodhd", "get_historical_dividends_data", {"ticker": "{ticker}.US"}),
    BaselineCall("eodhd", "financial_news", {"s": "{ticker}.US"}),
)


def materialize(catalog: tuple[BaselineCall, ...], *, ticker: str) -> list[BaselineCall]:
    """Substitute the {ticker} placeholder in args."""
    out: list[BaselineCall] = []
    for c in catalog:
        args = {
            k: (v.replace("{ticker}", ticker) if isinstance(v, str) else v)
            for k, v in c.args.items()
        }
        out.append(BaselineCall(provider=c.provider, tool=c.tool, args=args))
    return out


async def run_baseline(
    *,
    catalog: list[BaselineCall],
    dispatcher: ToolDispatcher,
) -> Manifest:
    """Dispatch every baseline call in parallel. Failed calls are skipped."""

    async def _one(call: BaselineCall) -> tuple[BaselineCall, Any]:
        try:
            result = await dispatcher.dispatch(call.provider, call.tool, call.args)
            return call, result
        except Exception:
            return call, None

    results = await asyncio.gather(*(_one(c) for c in catalog))
    manifest = Manifest()
    now = datetime.now(UTC).isoformat()
    for call, payload in results:
        if payload is None:
            continue
        manifest.append(
            kind="fetch",
            provider=call.provider,
            identifier=call.identifier(),
            raw_payload=payload,
            retrieved_at=now,
        )
    return manifest
