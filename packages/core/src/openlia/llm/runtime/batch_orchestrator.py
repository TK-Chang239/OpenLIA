"""Turn-synchronized batch orchestrator.

Drives a group of runs (each a ``RunStepper`` — e.g. ``EuRunState``)
together through a ``BatchTransport``. Each cycle:

  1. Collect every still-active run's next request (dropping any that
     became terminal, e.g. hit its turn cap).
  2. Submit them as ONE provider batch; persist the handle.
  3. Poll until the batch completes (or fails / expires / times out).
  4. Distribute results: each run ingests its response and runs its tools
     locally; runs that finalize drop out.

Runs finish at different turn counts — the next batch carries only the
still-active runs, so a fast 2-turn report doesn't wait on a slow 30-turn
one beyond the shared per-cycle latency. One run failing (bad result, an
exception in ``apply_response``) is isolated: it drops out, the rest
continue. A batch-level failure / expiry / wall-clock timeout fails every
still-active run.

Engine-agnostic: it knows only the ``RunStepper`` surface, so the same
orchestrator serves EU now and report_v3 later. Callbacks
(``on_turn_persisted`` / ``on_run_complete`` / ``on_run_failed``) are where
the server layer persists state and fires notifications; default no-ops
keep the core testable without a DB. ``sleep`` / ``now`` are injectable so
tests run instantly.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from openlia.llm.batch_transport import BatchRequestItem, BatchStatus, BatchTransport
from openlia.llm.types import LLMRequest, LLMResponse


class RunStepper(Protocol):
    """A run the orchestrator can drive one turn at a time."""

    custom_id: str

    @property
    def terminal(self) -> bool: ...

    def pending_request(self) -> LLMRequest | None: ...

    async def apply_response(self, response: LLMResponse) -> None: ...

    def result(self) -> Any: ...


# Callback aliases. Persisted/notify hooks are sync (DB writes); default
# no-ops keep the core engine usable without a server.
TurnPersistedFn = Callable[[str, dict[str, "RunStepper"]], None]
RunCompleteFn = Callable[[str, Any], None]
RunFailedFn = Callable[[str, str], None]

_DEFAULT_POLL_INTERVAL_S = 120.0
_DEFAULT_MAX_WAIT_S = 24 * 60 * 60  # provider batch SLA ceiling


def _noop_persisted(batch_id: str, active: dict[str, RunStepper]) -> None:
    del batch_id, active


def _noop_complete(custom_id: str, result: Any) -> None:
    del custom_id, result


def _noop_failed(custom_id: str, message: str) -> None:
    del custom_id, message


class BatchOrchestrator:
    """Run a group of ``RunStepper``s in lockstep over a ``BatchTransport``."""

    def __init__(
        self,
        *,
        transport: BatchTransport,
        runs: list[RunStepper],
        poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
        max_wait_s: float = _DEFAULT_MAX_WAIT_S,
        on_turn_persisted: TurnPersistedFn = _noop_persisted,
        on_run_complete: RunCompleteFn = _noop_complete,
        on_run_failed: RunFailedFn = _noop_failed,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._runs = runs
        self._poll_interval_s = poll_interval_s
        self._max_wait_s = max_wait_s
        self._on_turn_persisted = on_turn_persisted
        self._on_run_complete = on_run_complete
        self._on_run_failed = on_run_failed
        self._sleep = sleep
        self._now = now

    async def run(self) -> None:
        deadline = self._now() + self._max_wait_s
        active: dict[str, RunStepper] = {r.custom_id: r for r in self._runs}

        while active:
            # Build this cycle's batch; drop runs that became terminal at the
            # boundary (e.g. pending_request tripping the turn cap).
            items: list[BatchRequestItem] = []
            for cid, run in list(active.items()):
                req = run.pending_request()
                if req is None:
                    self._finalize(cid, run)
                    del active[cid]
                    continue
                items.append(BatchRequestItem(custom_id=cid, request=req))
            if not active:
                break

            batch_id = await self._transport.submit_batch(items)
            self._on_turn_persisted(batch_id, active)

            status = await self._await_batch(batch_id, deadline)
            if status is not BatchStatus.COMPLETED:
                self._fail_all(active, f"batch {batch_id} ended with status {status.value}")
                return

            results = await self._transport.fetch_results(batch_id)
            for cid, run in list(active.items()):
                res = results.get(cid)
                if res is None or res.error or res.response is None:
                    msg = res.error if res is not None and res.error else "no batch result"
                    self._on_run_failed(cid, msg)
                    del active[cid]
                    continue
                try:
                    await run.apply_response(res.response)
                except Exception as exc:  # isolate one bad run; the rest continue
                    self._on_run_failed(cid, f"apply_response failed: {exc}")
                    del active[cid]
                    continue
                if run.terminal:
                    self._finalize(cid, run)
                    del active[cid]

            self._on_turn_persisted(batch_id, active)

    async def _await_batch(self, batch_id: str, deadline: float) -> BatchStatus:
        """Poll until the batch leaves IN_PROGRESS, the deadline passes, or it fails."""
        while True:
            if self._now() > deadline:
                return BatchStatus.EXPIRED
            status = await self._transport.poll_batch(batch_id)
            if status is BatchStatus.COMPLETED:
                return status
            if status in (BatchStatus.FAILED, BatchStatus.EXPIRED):
                return status
            await self._sleep(self._poll_interval_s)

    def _finalize(self, custom_id: str, run: RunStepper) -> None:
        result = run.result()
        status = getattr(result, "status", None)
        if status == "completed":
            self._on_run_complete(custom_id, result)
        else:
            message = getattr(result, "message", "") or "run ended without completion"
            self._on_run_failed(custom_id, message)

    def _fail_all(self, active: dict[str, RunStepper], message: str) -> None:
        for cid in list(active):
            self._on_run_failed(cid, message)
        active.clear()


__all__ = ["BatchOrchestrator", "RunStepper"]
