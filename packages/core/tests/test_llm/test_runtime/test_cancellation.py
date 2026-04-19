from __future__ import annotations

import asyncio
import time

import pytest

from openlia.llm.runtime.cancellation import (
    CancellationToken,
    await_with_grace,
)

pytestmark = pytest.mark.asyncio


async def test_new_token_is_not_cancelled() -> None:
    tok = CancellationToken()
    assert tok.is_cancelled is False


async def test_cancel_sets_flag() -> None:
    tok = CancellationToken()
    tok.cancel()
    assert tok.is_cancelled is True


async def test_wait_returns_on_cancel() -> None:
    tok = CancellationToken()

    async def flip() -> None:
        await asyncio.sleep(0.01)
        tok.cancel()

    asyncio.create_task(flip())
    await asyncio.wait_for(tok.wait(), timeout=1.0)
    assert tok.is_cancelled is True


async def test_await_with_grace_returns_result_when_not_cancelled() -> None:
    tok = CancellationToken()

    async def slow() -> int:
        await asyncio.sleep(0.05)
        return 42

    result = await await_with_grace(slow(), token=tok, grace_seconds=1.0)
    assert result == 42


async def test_await_with_grace_cancels_after_grace_window() -> None:
    tok = CancellationToken()

    async def never_finishes() -> None:
        await asyncio.sleep(10)

    coro = never_finishes()
    tok.cancel()
    t0 = time.monotonic()
    with pytest.raises(asyncio.CancelledError):
        await await_with_grace(coro, token=tok, grace_seconds=0.2)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0  # definitely cancelled well before 10s


async def test_await_with_grace_still_returns_if_task_finishes_within_grace() -> None:
    tok = CancellationToken()

    async def finishes_fast() -> str:
        await asyncio.sleep(0.05)
        return "ok"

    coro = finishes_fast()
    tok.cancel()  # flipped before awaiting
    result = await await_with_grace(coro, token=tok, grace_seconds=1.0)
    assert result == "ok"
