from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from openlia.llm.exceptions import RateLimitError, is_transient

_BACKOFFS = (1.0, 4.0, 10.0)


async def with_retries[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_s: float = 1.0,
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            if not is_transient(exc):
                raise
            last_exc = exc
            if attempt >= max_attempts:
                break

            # Exponential backoff is scaled by base_delay_s, so setting
            # base_delay_s=0 disables the synthetic wait (e.g. in tests).
            backoff = _BACKOFFS[min(attempt - 1, len(_BACKOFFS) - 1)] * base_delay_s
            jitter = backoff * random.uniform(-0.2, 0.2)
            delay = max(0.0, backoff + jitter) if base_delay_s > 0 else 0.0

            # A genuine server-provided Retry-After is an explicit
            # instruction and is honored at face value regardless of
            # base_delay_s, so a real 429 never retries instantly.
            if isinstance(exc, RateLimitError) and exc.retry_after_seconds is not None:
                delay = max(delay, float(exc.retry_after_seconds))

            if delay > 0:
                await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
