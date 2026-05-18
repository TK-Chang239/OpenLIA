"""Provider adapters for WavedReportRunner writers.

Two concrete adapters wrapping ``LLMProvider.generate``:

- ``ProviderSectionWriter`` — plain text generation for body and synthesis sections.
- ``ProviderStructuredOutput`` — forced tool call for structured JSON output.

``tool_choice`` is sent in the OpenAI / OpenRouter shape::

    {"type": "function", "function": {"name": "<tool_name>"}}

Anthropic adapters expect ``{"type": "tool", "name": "..."}`` and Gemini uses
``{"function_calling_config": {...}}``.  The runtime / provider adapter is
responsible for translating this field before forwarding to the upstream API;
these classes pass it through verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message, ResolvedModel, ToolSchema


@dataclass
class ProviderSectionWriter:
    """Text writer for body / synthesis sections.

    No tools, no structured output — produces a single free-form Markdown
    string from ``provider.generate``.
    """

    provider: LLMProvider
    resolved_model: ResolvedModel
    max_tokens: int = 8192
    temperature: float = 0.7

    async def write(self, prompt: str) -> str:
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        response = await self.provider.generate(request)
        return response.text


@dataclass
class ProviderStructuredOutput:
    """Structured output via a forced tool call.

    The provider returns a single tool call whose ``arguments`` dict matches
    the JSON schema passed to ``structured_output``.  ``tool_choice`` uses the
    OpenAI / OpenRouter shape — see module docstring for per-provider notes.
    """

    provider: LLMProvider
    resolved_model: ResolvedModel
    tool_name: str = "emit"
    max_tokens: int = 4096
    temperature: float = 0.0

    async def structured_output(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        tool = ToolSchema(
            name=self.tool_name,
            description="Emit structured output matching the schema.",
            parameters=schema,
        )
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": self.tool_name}},
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        response = await self.provider.generate(request)
        if not response.tool_calls:
            raise RuntimeError(f"provider did not return a {self.tool_name!r} tool call")
        return response.tool_calls[0].arguments
