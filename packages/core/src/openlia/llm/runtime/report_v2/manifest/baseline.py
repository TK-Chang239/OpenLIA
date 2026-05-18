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
        ticker = self.args.get("ticker") or self.args.get("query") or ""
        return f"{self.tool}/{ticker}" if ticker else self.tool


BASELINE_STOCK_INITIATION: tuple[BaselineCall, ...] = (
    BaselineCall("eodhd", "get_live_prices", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_fundamentals_data", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_historical_market_cap", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_historical_prices", {"ticker": "{ticker}", "lookback": "60d"}),
    BaselineCall("eodhd", "get_historical_prices_long", {"ticker": "{ticker}", "lookback": "5y"}),
    BaselineCall("eodhd", "get_income_statement", {"ticker": "{ticker}", "years": 5}),
    BaselineCall("eodhd", "get_balance_sheet", {"ticker": "{ticker}", "years": 5}),
    BaselineCall("eodhd", "get_cash_flow", {"ticker": "{ticker}", "years": 5}),
    BaselineCall("eodhd", "get_earnings_trends", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_holders", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_insider_transactions", {"ticker": "{ticker}"}),
    BaselineCall("news", "recent_news", {"ticker": "{ticker}", "lookback_days": 30}),
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
