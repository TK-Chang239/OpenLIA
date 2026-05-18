from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.manifest.preflight import (
    PreflightDeclaration,
    run_section_preflight,
)


def _empty_manifest() -> Manifest:
    return Manifest()


@pytest.mark.asyncio
async def test_preflight_returns_structured_declaration() -> None:
    provider = AsyncMock()
    provider.structured_output.return_value = {
        "searches": [{"query": "cloudflare edge market share 2025", "intent": "TAM context"}],
        "fetches": [],
        "proposed_facts": ["edge_platform_tam"],
    }
    decl = await run_section_preflight(
        provider=provider,
        section_id="industry_overview",
        section_brief="Frame the edge / CDN industry.",
        manifest=_empty_manifest(),
        known_fact_names=["market_cap", "sector"],
    )
    assert isinstance(decl, PreflightDeclaration)
    assert decl.section_id == "industry_overview"
    assert decl.searches[0].query == "cloudflare edge market share 2025"
    assert decl.proposed_facts == ["edge_platform_tam"]


@pytest.mark.asyncio
async def test_preflight_provider_called_with_section_brief_and_existing_manifest() -> None:
    provider = AsyncMock()
    provider.structured_output.return_value = {"searches": [], "fetches": [], "proposed_facts": []}
    manifest = _empty_manifest()
    manifest.append(
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/NET.US",
        raw_payload={},
        retrieved_at="2026-05-17T20:00:00Z",
    )
    await run_section_preflight(
        provider=provider,
        section_id="financial_analysis",
        section_brief="Analyze 5y financials.",
        manifest=manifest,
        known_fact_names=["revenue_annual", "market_cap"],
    )
    call_kwargs = provider.structured_output.await_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "financial_analysis" in prompt
    assert "Analyze 5y financials" in prompt
    assert "[1] eodhd/get_fundamentals_data/NET.US" in prompt
    assert "revenue_annual" in prompt  # known facts listed
