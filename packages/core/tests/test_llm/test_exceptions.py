"""Typed-exception tests for the LLM provider surface."""

from __future__ import annotations

from openlia.llm.exceptions import (
    AuthError,
    CapabilityError,
    ContextLengthError,
    LLMProviderError,
    ModelNotFoundError,
    ProviderOutageError,
    RateLimitError,
    TransportError,
)


def test_all_errors_derive_from_llm_provider_error() -> None:
    for cls in (
        AuthError,
        CapabilityError,
        ContextLengthError,
        ModelNotFoundError,
        ProviderOutageError,
        RateLimitError,
        TransportError,
    ):
        assert issubclass(cls, LLMProviderError)


def test_rate_limit_retry_after_defaults_to_none() -> None:
    err = RateLimitError("slow down", retry_after_seconds=None)
    assert err.retry_after_seconds is None
    assert "slow down" in str(err)


def test_rate_limit_retry_after_roundtrip() -> None:
    err = RateLimitError("try again", retry_after_seconds=12)
    assert err.retry_after_seconds == 12


def test_auth_error_is_non_transient() -> None:
    from openlia.llm.exceptions import is_transient

    assert is_transient(AuthError("bad key")) is False
    assert is_transient(ModelNotFoundError("nope")) is False
    assert is_transient(CapabilityError("no tools")) is False
    assert is_transient(ContextLengthError("too long", limit=8000)) is False


def test_transport_and_rate_limit_and_outage_are_transient() -> None:
    from openlia.llm.exceptions import is_transient

    assert is_transient(TransportError("dns")) is True
    assert is_transient(RateLimitError("429", retry_after_seconds=1)) is True
    assert is_transient(ProviderOutageError("5xx")) is True


def test_context_length_exposes_limit() -> None:
    err = ContextLengthError("too long", limit=8192)
    assert err.limit == 8192
