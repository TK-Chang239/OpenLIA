from __future__ import annotations

import re
from dataclasses import replace

from openlia.llm.types import Capabilities

_DEFAULT = Capabilities()

_OPENAI_COMPAT_DEFAULT = Capabilities(
    streaming=True,
    tool_calling=True,
    structured_output=True,
    vision=False,
    web_search_native=False,
    max_context_tokens=32_000,
    max_output_tokens=4_096,
)


def _anthropic_opus() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=200_000,
        max_output_tokens=8_192,
    )


def _anthropic_sonnet() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=200_000,
        max_output_tokens=8_192,
    )


def _anthropic_haiku() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=False,
        max_context_tokens=200_000,
        max_output_tokens=4_096,
    )


def _openai_gpt_5_4_pro() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=400_000,
        max_output_tokens=16_384,
    )


def _openai_gpt_5_4() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=200_000,
        max_output_tokens=8_192,
    )


def _openai_gpt_5_4_mini() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=False,
        max_context_tokens=128_000,
        max_output_tokens=4_096,
    )


def _gemini_pro() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=1_000_000,
        max_output_tokens=8_192,
    )


def _gemini_flash() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=1_000_000,
        max_output_tokens=8_192,
    )


def _gemini_flash_lite() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=False,
        max_context_tokens=500_000,
        max_output_tokens=4_096,
    )


def _ollama_tool_family() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=False,
        vision=False,
        web_search_native=False,
        max_context_tokens=128_000,
        max_output_tokens=4_096,
    )


_CAPABILITY_MAP: list[tuple[str, re.Pattern[str], object]] = [
    ("anthropic", re.compile(r"^claude-opus-4", re.IGNORECASE), _anthropic_opus),
    ("anthropic", re.compile(r"^claude-sonnet-4", re.IGNORECASE), _anthropic_sonnet),
    ("anthropic", re.compile(r"^claude-haiku-4", re.IGNORECASE), _anthropic_haiku),
    ("openai", re.compile(r"^gpt-5\.4-pro", re.IGNORECASE), _openai_gpt_5_4_pro),
    ("openai", re.compile(r"^gpt-5\.4-mini", re.IGNORECASE), _openai_gpt_5_4_mini),
    ("openai", re.compile(r"^gpt-5\.4", re.IGNORECASE), _openai_gpt_5_4),
    ("gemini", re.compile(r"^gemini-3\.1-pro", re.IGNORECASE), _gemini_pro),
    ("gemini", re.compile(r"^gemini-3\.1-flash-lite", re.IGNORECASE), _gemini_flash_lite),
    ("gemini", re.compile(r"^gemini-3\.1-flash", re.IGNORECASE), _gemini_flash),
    ("gemini", re.compile(r"^gemini-3-flash", re.IGNORECASE), _gemini_flash),
    ("ollama", re.compile(r"^llama3\.1", re.IGNORECASE), _ollama_tool_family),
    ("ollama", re.compile(r"^qwen2\.5", re.IGNORECASE), _ollama_tool_family),
    ("ollama", re.compile(r"^mistral-nemo", re.IGNORECASE), _ollama_tool_family),
]


def _lookup_base(provider_kind: str, model: str) -> Capabilities:
    if provider_kind == "openrouter" and "/" in model:
        upstream_kind, upstream_model = model.split("/", 1)
        return _lookup_base(upstream_kind, upstream_model)

    if provider_kind == "openai_compat":
        return _OPENAI_COMPAT_DEFAULT

    for kind, pattern, factory in _CAPABILITY_MAP:
        if kind == provider_kind and pattern.match(model):
            return factory()  # type: ignore[operator]

    return _DEFAULT


def capabilities_for(
    *,
    provider_kind: str,
    model: str,
    override: dict | None = None,
) -> Capabilities:
    base = _lookup_base(provider_kind, model)
    if not override:
        return base
    fields = {
        "streaming",
        "tool_calling",
        "structured_output",
        "vision",
        "web_search_native",
        "max_context_tokens",
        "max_output_tokens",
    }
    patch = {k: v for k, v in override.items() if k in fields}
    return replace(base, **patch)
