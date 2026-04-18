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
