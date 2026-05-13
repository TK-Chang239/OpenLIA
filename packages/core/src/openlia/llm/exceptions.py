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


class ModelNotConfiguredError(Exception):
    """No model has been assigned to a slot in `llm_slot_defaults`.

    Raised by the resolver when no per-user override, no per-department
    user pref, and no admin-assigned slot default exists. The message
    directs the operator to the Settings page.
    """

    def __init__(self, *, slot_kind: str, slot_id: str) -> None:
        self.slot_kind = slot_kind
        self.slot_id = slot_id
        super().__init__(
            f"No model is configured for {slot_kind}={slot_id!r}. "
            f"Assign one in Settings → Models."
        )


_TRANSIENT: tuple[type[LLMProviderError], ...] = (
    TransportError,
    RateLimitError,
    ProviderOutageError,
)


def is_transient(exc: BaseException) -> bool:
    """True if the exception should be retried by the adapter layer."""
    return isinstance(exc, _TRANSIENT)
