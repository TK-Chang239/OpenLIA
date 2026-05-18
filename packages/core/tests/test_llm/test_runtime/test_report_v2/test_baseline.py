from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.report_v2.manifest.baseline import (
    BASELINE_STOCK_INITIATION,
    BaselineCall,
    run_baseline,
)


def test_baseline_catalog_has_expected_calls() -> None:
    names = {(c.provider, c.tool) for c in BASELINE_STOCK_INITIATION}
    assert ("eodhd", "get_fundamentals_data") in names
    assert ("eodhd", "get_holders") in names
    assert ("eodhd", "get_insider_transactions") in names
    assert ("eodhd", "get_historical_prices") in names
    assert ("eodhd", "get_live_prices") in names
    assert ("news", "recent_news") in names
    assert len(BASELINE_STOCK_INITIATION) >= 10


@pytest.mark.asyncio
async def test_run_baseline_dispatches_each_call_in_parallel() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: {
        "called": f"{provider}.{tool}",
        "args": args,
    }
    catalog = [
        BaselineCall(provider="eodhd", tool="get_fundamentals_data", args={"ticker": "NET.US"}),
        BaselineCall(provider="eodhd", tool="get_holders", args={"ticker": "NET.US"}),
    ]
    manifest = await run_baseline(catalog=catalog, dispatcher=dispatcher)
    assert len(manifest) == 2
    assert manifest.entries[0].identifier == "get_fundamentals_data/NET.US"
    assert manifest.entries[1].identifier == "get_holders/NET.US"
    assert dispatcher.dispatch.await_count == 2


@pytest.mark.asyncio
async def test_run_baseline_skips_failed_calls_records_in_telemetry() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = [
        {"ok": True},
        RuntimeError("provider down"),
    ]
    catalog = [
        BaselineCall(provider="eodhd", tool="get_fundamentals_data", args={"ticker": "NET.US"}),
        BaselineCall(provider="eodhd", tool="get_holders", args={"ticker": "NET.US"}),
    ]
    manifest = await run_baseline(catalog=catalog, dispatcher=dispatcher)
    assert len(manifest) == 1
    assert manifest.entries[0].identifier == "get_fundamentals_data/NET.US"
