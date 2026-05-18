from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.report_v2.manifest.aggregator import (
    AggregatedWork,
    aggregate_declarations,
    execute_aggregated,
)
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.manifest.preflight import (
    PreflightDeclaration,
    PreflightFetch,
    PreflightSearch,
)


def test_aggregate_dedupes_identical_searches() -> None:
    decls = [
        PreflightDeclaration(
            section_id="a",
            searches=[PreflightSearch(query="edge market 2025", intent="x")],
            fetches=[],
        ),
        PreflightDeclaration(
            section_id="b",
            searches=[PreflightSearch(query="edge market 2025", intent="y")],
            fetches=[],
        ),
    ]
    agg = aggregate_declarations(decls)
    assert len(agg.searches) == 1
    assert {"a", "b"} == set(agg.search_intents["edge market 2025"])


def test_aggregate_dedupes_identical_fetches_by_provider_tool_args() -> None:
    decls = [
        PreflightDeclaration(
            section_id="a",
            fetches=[PreflightFetch(provider="eodhd", tool="get_x", args={"ticker": "NET.US"})],
        ),
        PreflightDeclaration(
            section_id="b",
            fetches=[PreflightFetch(provider="eodhd", tool="get_x", args={"ticker": "NET.US"})],
        ),
        PreflightDeclaration(
            section_id="c",
            fetches=[PreflightFetch(provider="eodhd", tool="get_x", args={"ticker": "AAPL.US"})],
        ),
    ]
    agg = aggregate_declarations(decls)
    assert len(agg.fetches) == 2


def test_proposed_facts_collected_per_section_for_telemetry() -> None:
    decls = [
        PreflightDeclaration(section_id="industry_overview", proposed_facts=["edge_tam"]),
        PreflightDeclaration(
            section_id="competitive_analysis",
            proposed_facts=["edge_tam", "peer_revenue_growth"],
        ),
    ]
    agg = aggregate_declarations(decls)
    assert agg.proposed_facts["industry_overview"] == ["edge_tam"]
    assert set(agg.proposed_facts["competitive_analysis"]) == {"edge_tam", "peer_revenue_growth"}


@pytest.mark.asyncio
async def test_execute_aggregated_dispatches_and_extends_manifest() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: {"r": f"{tool}-{args}"}
    websearch = AsyncMock()
    websearch.search.side_effect = lambda query: [{"title": f"hit for {query}", "url": "https://x"}]

    agg = AggregatedWork(
        searches=["edge market 2025"],
        search_intents={"edge market 2025": ["a"]},
        fetches=[("eodhd", "get_x", {"ticker": "NET.US"})],
        proposed_facts={},
    )
    manifest = Manifest()
    manifest.append(
        kind="fetch", provider="eodhd", identifier="baseline/x", raw_payload={}, retrieved_at="t"
    )
    await execute_aggregated(
        work=agg, manifest=manifest, dispatcher=dispatcher, websearch=websearch
    )
    assert len(manifest) == 3  # 1 baseline + 1 fetch + 1 search
    identifiers = [e.identifier for e in manifest.entries]
    assert "get_x/NET.US" in identifiers
    assert "edge market 2025" in identifiers
