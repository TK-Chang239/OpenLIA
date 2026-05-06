from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ModelTier(StrEnum):
    THINKING = "thinking"
    EVERYDAY = "everyday"
    QUICK = "quick"


class Capability(StrEnum):
    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    VISION = "vision"
    WEB_SEARCH = "web_search"


@dataclass(frozen=True)
class Capabilities:
    streaming: bool = True
    tool_calling: bool = False
    structured_output: bool = False
    vision: bool = False
    web_search_native: bool = False
    max_context_tokens: int = 8192
    max_output_tokens: int = 2048


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    # Set on role="tool" messages to pair the result with the originating
    # tool call. Adapters need this so the upstream protocol (OpenAI-style
    # chat completions, Anthropic Claude tool_use, etc.) can match the
    # response back to the assistant turn that requested it.
    tool_call_id: str | None = None
    # Set on role="assistant" messages that carry tool calls. Required for
    # multi-turn tool-use loops: the assistant message that emitted tool
    # calls must be replayed back to the model alongside the tool results.
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class ResponseFormat:
    kind: str
    json_schema: dict | None = None


@dataclass(frozen=True)
class LLMRequest:
    messages: list[Message]
    system: str | None = None
    tools: list[ToolSchema] | None = None
    response_format: ResponseFormat | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    stop: list[str] | None = None
    # Provider-specific tool selection directive. When set, the request
    # forces or biases the model toward a specific tool. Each adapter
    # forwards this verbatim to its upstream API, so callers must use
    # the upstream's expected shape:
    #   OpenAI / OpenRouter (chat.completions): {"type": "function", "function": {"name": "..."}}
    #   Anthropic (messages):                   {"type": "tool", "name": "..."}
    #   Gemini (generateContent):               {"function_calling_config": {"mode": "ANY"|"AUTO"|"NONE", "allowed_function_names": [...]}}
    # `None` means no constraint (model decides).
    tool_choice: dict | None = None


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class LLMResponse:
    text: str
    finish_reason: str
    input_tokens: int
    output_tokens: int
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class LLMChunk:
    delta: str
    finish_reason: str | None = None


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    context_window: int | None = None


@dataclass(frozen=True)
class ProviderCredentials:
    api_key: str | None
    base_url: str | None


@dataclass(frozen=True)
class TestResult:
    ok: bool
    latency_ms: int
    error_class: str | None
    error_msg: str | None


@dataclass(frozen=True)
class DepartmentRequirements:
    required: list[Capability]
    preferred: list[Capability] = field(default_factory=list)
    min_output_tokens: int = 0
    min_context_tokens: int = 0


@dataclass(frozen=True)
class ResolvedModel:
    provider_kind: str
    provider_id: str
    model_id: str
    model_ref: str
    tier: ModelTier
    credentials: ProviderCredentials
    capabilities: Capabilities
    overrides: dict
