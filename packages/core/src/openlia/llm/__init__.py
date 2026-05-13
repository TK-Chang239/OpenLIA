from __future__ import annotations

from openlia.llm.adapters import (
    ADAPTERS,
    AnthropicAdapter,
    GeminiAdapter,
    OllamaAdapter,
    OpenAIAdapter,
    OpenAICompatAdapter,
    OpenRouterAdapter,
    build_adapter,
)
from openlia.llm.base import LLMProvider
from openlia.llm.capabilities import (
    CapabilityReport,
    capabilities_for,
    evaluate_requirements,
)
from openlia.llm.department_defaults import (
    DEPARTMENT_DEFAULT_TIERS,
    DEPARTMENT_TIER_REASONS,
)
from openlia.llm.department_requirements import (
    DEPARTMENT_REQUIREMENTS,
    requirements_for,
)
from openlia.llm.exceptions import (
    AuthError,
    CapabilityError,
    ContextLengthError,
    LLMProviderError,
    ModelNotConfiguredError,
    ModelNotFoundError,
    ProviderOutageError,
    RateLimitError,
    TransportError,
    is_transient,
)
from openlia.llm.model_defaults import SHIPPED_TIER_DEFAULTS
from openlia.llm.resolver import (
    ModelRegistry,
    ResolvedModelRow,
    resolve,
    resolve_tier,
)
from openlia.llm.retry import with_retries
from openlia.llm.types import (
    Capabilities,
    Capability,
    DepartmentRequirements,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
    ResponseFormat,
    TestResult,
    ToolCall,
    ToolSchema,
)

__all__ = [
    "ADAPTERS",
    "DEPARTMENT_DEFAULT_TIERS",
    "DEPARTMENT_REQUIREMENTS",
    "DEPARTMENT_TIER_REASONS",
    "SHIPPED_TIER_DEFAULTS",
    "AnthropicAdapter",
    "AuthError",
    "Capabilities",
    "Capability",
    "CapabilityError",
    "CapabilityReport",
    "ContextLengthError",
    "DepartmentRequirements",
    "GeminiAdapter",
    "LLMChunk",
    "LLMProvider",
    "LLMProviderError",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "ModelInfo",
    "ModelNotConfiguredError",
    "ModelNotFoundError",
    "ModelRegistry",
    "ModelTier",
    "OllamaAdapter",
    "OpenAIAdapter",
    "OpenAICompatAdapter",
    "OpenRouterAdapter",
    "ProviderCredentials",
    "ProviderOutageError",
    "RateLimitError",
    "ResolvedModel",
    "ResolvedModelRow",
    "ResponseFormat",
    "TestResult",
    "ToolCall",
    "ToolSchema",
    "TransportError",
    "build_adapter",
    "capabilities_for",
    "evaluate_requirements",
    "is_transient",
    "requirements_for",
    "resolve",
    "resolve_tier",
    "with_retries",
]
