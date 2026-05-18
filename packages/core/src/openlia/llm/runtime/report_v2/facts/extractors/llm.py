"""LLM-tier extractor — wraps a structured-output call against a small per-fact schema.

The provider protocol is intentionally narrow: structured_output(prompt, schema) -> dict.
Phase 5 wires this to the real provider; Phase 1 tests use AsyncMock.
"""
from __future__ import annotations

from typing import Any, Protocol

from openlia.llm.runtime.report_v2.types import Fact


class StructuredOutputProvider(Protocol):
    async def structured_output(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


async def llm_extract(
    *,
    provider: StructuredOutputProvider,
    fact_name: str,
    prompt: str,
    output_schema: dict[str, Any],
    source_ids: list[int],
) -> Fact:
    value = await provider.structured_output(prompt=prompt, schema=output_schema)
    return Fact(
        name=fact_name,
        value=value,
        source_ids=sorted(set(source_ids)),
        extractor="llm",
    )
