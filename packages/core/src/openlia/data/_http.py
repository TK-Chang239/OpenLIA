"""HTTP retry/backoff helper shared by data adapters.

The adapter is the only layer that has the `Retry-After` header in scope,
so retry has to live here (Plan 5's dispatch layer cannot retry without
re-fetching the response).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx

from openlia.data.errors import RateLimitError


async def async_request_with_retry(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    provider_kind: str,
    max_attempts: int = 3,
    base_backoff: float = 0.5,
    rate_limit_classifier: Callable[[httpx.Response], int | None] | None = None,
) -> httpx.Response:
    """Call `send()` with retry on RateLimitError-equivalent responses.

    `rate_limit_classifier(resp)` returns retry-after seconds (or None) for
    a 429-like response, or returns -1 to indicate "not a rate limit". When
    None or missing, exponential backoff with jitter is used. When all
    attempts are exhausted, the final RateLimitError is re-raised.
    """
    last_error: RateLimitError | None = None
    for attempt in range(max_attempts):
        resp = await send()
        if rate_limit_classifier is None:
            return resp
        retry_after = rate_limit_classifier(resp)
        if retry_after is None:
            return resp  # not rate limited
        last_error = RateLimitError(
            provider_kind=provider_kind,
            retry_after_seconds=retry_after if retry_after >= 0 else None,
        )
        if attempt == max_attempts - 1:
            break
        delay = (
            float(retry_after)
            if retry_after >= 0
            else base_backoff * (2**attempt) + random.uniform(0, base_backoff)
        )
        await asyncio.sleep(min(delay, 60.0))
    assert last_error is not None
    raise last_error
