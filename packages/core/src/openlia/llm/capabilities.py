from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from openlia.llm.types import Capabilities, Capability, DepartmentRequirements

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
        pdf_native=True,
        max_context_tokens=200_000,
        max_output_tokens=32_000,
    )


def _anthropic_sonnet() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        pdf_native=True,
        max_context_tokens=200_000,
        max_output_tokens=64_000,
    )


def _anthropic_haiku() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=False,
        pdf_native=True,
        max_context_tokens=200_000,
        max_output_tokens=16_000,
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
        max_output_tokens=128_000,
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
        pdf_native=True,
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
        pdf_native=True,
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
        pdf_native=True,
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
    # ``-latest`` (and bare ``-opus``/``-sonnet``/``-haiku``) cover OpenRouter
    # floating-version aliases like ``anthropic/claude-sonnet-latest``.
    ("anthropic", re.compile(r"^claude-opus(-|$)", re.IGNORECASE), _anthropic_opus),
    ("anthropic", re.compile(r"^claude-sonnet(-|$)", re.IGNORECASE), _anthropic_sonnet),
    ("anthropic", re.compile(r"^claude-haiku(-|$)", re.IGNORECASE), _anthropic_haiku),
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
        # OpenRouter prefixes some routes with ``~`` to denote a floating
        # alias (e.g. ``~anthropic/claude-sonnet-latest``). Strip it so the
        # upstream-kind lookup matches a real provider.
        upstream_kind = upstream_kind.lstrip("~")
        upstream = _lookup_base(upstream_kind, upstream_model)
        # Issue #99 follow-up: even when the upstream model accepts native
        # PDFs, the OpenRouter adapter renders our DocumentBlock as an
        # OpenAI-style "[Document content not natively supported]" placeholder
        # because OpenRouter's relay doesn't pass through Anthropic
        # document blocks. Force ``pdf_native=False`` so the materializer
        # uses extracted text until the adapter learns OpenRouter's
        # PDF-file-input shape.
        return replace(upstream, pdf_native=False)

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


@dataclass(frozen=True)
class CapabilityReport:
    status: str
    missing_required: list[Capability] = field(default_factory=list)
    missing_preferred: list[Capability] = field(default_factory=list)
    insufficient_context_tokens: int | None = None
    insufficient_output_tokens: int | None = None


_CAP_TO_FIELD: dict[Capability, str] = {
    Capability.STREAMING: "streaming",
    Capability.TOOL_CALLING: "tool_calling",
    Capability.STRUCTURED_OUTPUT: "structured_output",
    Capability.VISION: "vision",
    Capability.WEB_SEARCH: "web_search_native",
}


def _has_capability(caps: Capabilities, cap: Capability) -> bool:
    return bool(getattr(caps, _CAP_TO_FIELD[cap], False))


def evaluate_requirements(
    caps: Capabilities,
    requirements: DepartmentRequirements,
) -> CapabilityReport:
    """Score a Capabilities snapshot against DepartmentRequirements.

    Returns ready when all required + token minimums met; amber when only preferred
    capabilities are missing; blocked when any required capability or minimum is unmet.
    """
    missing_required = [c for c in requirements.required if not _has_capability(caps, c)]
    missing_preferred = [c for c in requirements.preferred if not _has_capability(caps, c)]
    insufficient_context = (
        requirements.min_context_tokens
        if requirements.min_context_tokens > caps.max_context_tokens
        else None
    )
    insufficient_output = (
        requirements.min_output_tokens
        if requirements.min_output_tokens > caps.max_output_tokens
        else None
    )

    if missing_required or insufficient_context is not None or insufficient_output is not None:
        status = "blocked"
    elif missing_preferred:
        status = "amber"
    else:
        status = "ready"

    return CapabilityReport(
        status=status,
        missing_required=missing_required,
        missing_preferred=missing_preferred,
        insufficient_context_tokens=insufficient_context,
        insufficient_output_tokens=insufficient_output,
    )
