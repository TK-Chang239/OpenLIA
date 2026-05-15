from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


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
    pdf_native: bool = False
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
    # Materialized attachment content blocks rendered alongside the user
    # text. Element type is the runtime ``ContentBlock`` union; declared
    # as ``tuple`` here to avoid an import cycle with the runtime layer.
    content_blocks: tuple = field(default_factory=tuple)


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
    #   Gemini (generateContent):
    #     {"function_calling_config":
    #       {"mode": "ANY"|"AUTO"|"NONE", "allowed_function_names": [...]}}
    # `None` means no constraint (model decides).
    tool_choice: dict | None = None
    # Canonical names of tools the runtime wants the adapter to satisfy
    # via the provider's native server-side mechanism instead of the
    # standard function-tool envelope. Today only "web_search" is
    # recognized; adapters swap the generic ToolSchema for the
    # provider-native form (e.g. `{"type": "web_search_20250305", ...}`
    # on Anthropic, `{"google_search": {}}` on Gemini,
    # `{"type": "web_search"}` on OpenAI Responses).
    native_tools: tuple[str, ...] = ()
    # Per-run cap on native web_search invocations. Anthropic enforces
    # this server-side via the tool block's `max_uses`; Gemini and
    # OpenAI have no equivalent so the runtime enforces softly via
    # the dispatcher's per-run counter. `None` means no cap.
    web_search_max_uses: int | None = None


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class Citation:
    """Provider-agnostic source reference attached to LLMResponse and,
    downstream, to ReportSchema. One Citation per tool result or
    web-search result the runtime observes.

    `kind` distinguishes:
      - "tool"   structured connector call; tool_name + tool_args identify it
      - "web"    web search result; url + title + source populated
      - "memory" model-knowledge fallback; source="model_knowledge" with
                 `date` marking the staleness boundary
    """

    id: str
    kind: str
    tool_name: str | None = None
    tool_args: dict | None = None
    url: str | None = None
    title: str | None = None
    source: str | None = None
    date: str | None = None
    snippet: str | None = None
    segment_start: int | None = None
    segment_end: int | None = None


@dataclass(frozen=True)
class ServerToolCall:
    """Telemetry record of a provider-side tool invocation the runtime
    did NOT dispatch itself (native web_search). Never enters
    ``ToolDispatcher.dispatch()``."""

    name: str
    arguments: dict
    turn_idx: int


@dataclass(frozen=True)
class FailedSearch:
    """Adapter-detected native search failure. Runtime rewrites each
    entry into a configured-adapter ToolCall when a fallback is
    available (the I-a rescue path). Single rewrite per (turn_idx,
    query) — no retry loop."""

    query: str
    error_kind: str
    error_message: str
    turn_idx: int


@dataclass(frozen=True)
class ServerToolEvent:
    """Streaming marker for provider-side tool activity. Surfaced
    through ``LLMChunk.server_tool_event`` so the runtime can emit
    SSE frames without each adapter knowing the wire format."""

    kind: str
    provider: str
    query: str | None = None
    urls: tuple[str, ...] = ()
    n_results: int | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    finish_reason: str
    input_tokens: int
    output_tokens: int
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Source references collected from native tool results (kind="tool")
    # and web search results (kind="web"). Empty tuple for adapters that
    # do not yet emit citations; the runtime treats absence as "no
    # provider-side citations" and falls back to inline-marker parsing.
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    # Provider-side tool invocations recorded for telemetry only.
    server_tool_calls: tuple[ServerToolCall, ...] = field(default_factory=tuple)
    # Provider-side tool failures the runtime should consider rewriting
    # into configured-adapter calls. See `FailedSearch` and the I-a
    # rescue path in ReportRunner.
    server_tool_failures: tuple[FailedSearch, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LLMChunk:
    delta: str
    finish_reason: str | None = None
    # Adapter-emitted markers for provider-side tool activity. Runtime
    # translates these to SSE events (WebSearchInvoked /
    # WebSearchCompleted). `None` on text-only chunks.
    server_tool_event: ServerToolEvent | None = None


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    context_window: int | None = None


@dataclass(frozen=True)
class ProviderCredentials:
    api_key: str | None
    base_url: str | None
    env_var_name: str | None = None


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
    credentials: ProviderCredentials
    capabilities: Capabilities
    overrides: dict
