"""Tests for report_v2/writers.py — provider adapters wired to LLMProvider.generate."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.report_v2.writers import (
    ProviderSectionWriter,
    ProviderStructuredOutput,
)
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    LLMResponse,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)


def _resolved_model() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="openai",
        provider_id="openai",
        model_id="gpt-4o",
        model_ref="openai/gpt-4o",
        credentials=ProviderCredentials(api_key="test-key", base_url=None),
        capabilities=Capabilities(),
        overrides={},
    )


def _llm_response(text: str = "", tool_calls: list[ToolCall] | None = None) -> LLMResponse:
    return LLMResponse(
        text=text,
        finish_reason="stop",
        input_tokens=10,
        output_tokens=20,
        tool_calls=tool_calls or [],
    )


@pytest.mark.asyncio
async def test_provider_section_writer_calls_provider_generate_returns_text() -> None:
    provider = AsyncMock()
    provider.generate.return_value = _llm_response(text="Analytical content here.")

    writer = ProviderSectionWriter(
        provider=provider,
        resolved_model=_resolved_model(),
    )
    result = await writer.write("Write a company overview.")

    assert result == "Analytical content here."
    provider.generate.assert_called_once()
    call_args = provider.generate.call_args[0][0]
    assert isinstance(call_args, LLMRequest)
    assert len(call_args.messages) == 1
    assert call_args.messages[0].role == "user"
    assert call_args.messages[0].content == "Write a company overview."
    assert call_args.max_tokens == 8192
    assert call_args.temperature == 0.7


@pytest.mark.asyncio
async def test_provider_structured_output_extracts_tool_call_arguments() -> None:
    expected = {"rating": "buy", "price_target": 120.0}
    tool_call = ToolCall(id="call_abc", name="emit", arguments=expected)
    provider = AsyncMock()
    provider.kind = "openai"
    provider.generate.return_value = _llm_response(tool_calls=[tool_call])

    structured = ProviderStructuredOutput(
        provider=provider,
        resolved_model=_resolved_model(),
    )
    schema = {
        "type": "object",
        "properties": {
            "rating": {"type": "string"},
            "price_target": {"type": "number"},
        },
        "required": ["rating", "price_target"],
    }
    result = await structured.structured_output(prompt="Emit a rating.", schema=schema)

    assert result == expected
    provider.generate.assert_called_once()
    call_args = provider.generate.call_args[0][0]
    assert isinstance(call_args, LLMRequest)
    assert call_args.tools is not None
    assert len(call_args.tools) == 1
    assert call_args.tools[0].name == "emit"
    assert call_args.tools[0].parameters == schema
    assert call_args.tool_choice == {"type": "function", "function": {"name": "emit"}}
    assert call_args.temperature == 0.0


@pytest.mark.asyncio
async def test_provider_structured_output_anthropic_uses_correct_tool_choice() -> None:
    tool_call = ToolCall(id="call_ant", name="emit", arguments={"value": 1})
    provider = AsyncMock()
    provider.kind = "anthropic"
    provider.generate.return_value = _llm_response(tool_calls=[tool_call])

    structured = ProviderStructuredOutput(
        provider=provider,
        resolved_model=_resolved_model(),
    )
    await structured.structured_output(
        prompt="Emit something.",
        schema={"type": "object", "properties": {"value": {"type": "integer"}}},
    )

    call_args = provider.generate.call_args[0][0]
    assert isinstance(call_args, LLMRequest)
    assert call_args.tool_choice == {"type": "tool", "name": "emit"}


@pytest.mark.asyncio
async def test_provider_structured_output_gemini_uses_correct_tool_choice() -> None:
    tool_call = ToolCall(id="call_gem", name="emit", arguments={"value": 2})
    provider = AsyncMock()
    provider.kind = "gemini"
    provider.generate.return_value = _llm_response(tool_calls=[tool_call])

    structured = ProviderStructuredOutput(
        provider=provider,
        resolved_model=_resolved_model(),
    )
    await structured.structured_output(
        prompt="Emit something.",
        schema={"type": "object", "properties": {"value": {"type": "integer"}}},
    )

    call_args = provider.generate.call_args[0][0]
    assert isinstance(call_args, LLMRequest)
    assert call_args.tool_choice == {
        "function_calling_config": {
            "mode": "ANY",
            "allowed_function_names": ["emit"],
        }
    }
