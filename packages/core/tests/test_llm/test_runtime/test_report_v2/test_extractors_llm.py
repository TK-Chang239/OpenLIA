from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.report_v2.facts.extractors.llm import llm_extract


@pytest.mark.asyncio
async def test_llm_extract_calls_provider_with_schema_and_returns_fact() -> None:
    mock_provider = AsyncMock()
    mock_provider.structured_output.return_value = {"peer_tickers": ["AKAM", "FSLY", "NET"]}

    schema = {
        "type": "object",
        "properties": {"peer_tickers": {"type": "array", "items": {"type": "string"}}},
    }
    fact = await llm_extract(
        provider=mock_provider,
        fact_name="peer_set",
        prompt="Identify peer companies for Cloudflare in the CDN/edge space.",
        output_schema=schema,
        source_ids=[1, 3],
    )
    assert fact.name == "peer_set"
    assert fact.value == {"peer_tickers": ["AKAM", "FSLY", "NET"]}
    assert fact.source_ids == [1, 3]
    assert fact.extractor == "llm"
    mock_provider.structured_output.assert_awaited_once()
