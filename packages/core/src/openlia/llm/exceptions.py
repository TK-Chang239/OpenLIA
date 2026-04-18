from __future__ import annotations


class LLMProviderError(Exception):
    """Base class for every error surfaced by the LLM provider layer."""


class TransportError(LLMProviderError):
    """Connection reset, read timeout, DNS failure, any other transport fault."""


class RateLimitError(LLMProviderError):
    """HTTP 429 (or provider-specific equivalent). Carries optional Retry-After seconds."""

    def __init__(self, message: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderOutageError(LLMProviderError):
    """Upstream gateway / 5xx. The provider is having a bad day, not the caller."""


class AuthError(LLMProviderError):
    """HTTP 401 / 403. The configured API key is invalid or revoked."""


class ModelNotFoundError(LLMProviderError):
    """HTTP 404 on completion, Ollama 'model not found', etc."""


class ContextLengthError(LLMProviderError):
    """Request exceeded the model's context window."""

    def __init__(self, message: str, *, limit: int) -> None:
        super().__init__(message)
        self.limit = limit


class CapabilityError(LLMProviderError):
    """Provider rejected a capability (tools / JSON / vision) the caller depended on."""


class TierNotConfiguredError(LLMProviderError):
    """The resolved tier has zero enabled models. The caller cannot proceed."""

    def __init__(self, tier: str) -> None:
        super().__init__(
            f"No enabled models configured in tier '{tier}'. "
            "Ask your admin to add one in Settings -> Admin -> Models."
        )
        self.tier = tier


_TRANSIENT: tuple[type[LLMProviderError], ...] = (
    TransportError,
    RateLimitError,
    ProviderOutageError,
)


def is_transient(exc: BaseException) -> bool:
    """True if the exception should be retried by the adapter layer."""
    return isinstance(exc, _TRANSIENT)
