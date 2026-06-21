from __future__ import annotations

import pytest
from openlia.llm.exceptions import (
    AuthError,
    ProviderOutageError,
    RateLimitError,
    TransportError,
)
from openlia.llm.retry import with_retries


async def _factory(responses):
    calls = {"n": 0}

    async def impl():
        calls["n"] += 1
        resp = responses[calls["n"] - 1]
        if isinstance(resp, Exception):
            raise resp
        return resp

    return impl, calls


async def test_returns_on_first_success() -> None:
    impl, calls = await _factory(["ok"])
    result = await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert result == "ok"
    assert calls["n"] == 1


async def test_retries_transport_up_to_three_times() -> None:
    impl, calls = await _factory([TransportError("boom"), TransportError("boom"), "ok"])
    result = await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert result == "ok"
    assert calls["n"] == 3


async def test_retries_outage_then_gives_up() -> None:
    impl, calls = await _factory(
        [
            ProviderOutageError("5xx"),
            ProviderOutageError("5xx"),
            ProviderOutageError("5xx"),
        ]
    )
    with pytest.raises(ProviderOutageError):
        await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert calls["n"] == 3


async def test_rate_limit_respects_retry_after() -> None:
    impl, calls = await _factory([RateLimitError("429", retry_after_seconds=0), "ok"])
    result = await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert result == "ok"
    assert calls["n"] == 2


async def test_retry_after_honored_even_when_base_delay_zero(monkeypatch) -> None:
    """A 429 carrying a positive Retry-After must wait that long even when
    base_delay_s=0 disables the synthetic exponential backoff. Otherwise a
    rate-limited provider gets hammered with an instant retry."""
    slept: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("openlia.llm.retry.asyncio.sleep", _fake_sleep)

    impl, calls = await _factory([RateLimitError("429", retry_after_seconds=7), "ok"])
    result = await with_retries(impl, max_attempts=3, base_delay_s=0)

    assert result == "ok"
    assert calls["n"] == 2
    assert slept == [7.0]  # honored at face value, not zeroed by base_delay_s=0


async def test_non_transient_not_retried() -> None:
    impl, calls = await _factory([AuthError("bad key")])
    with pytest.raises(AuthError):
        await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert calls["n"] == 1
