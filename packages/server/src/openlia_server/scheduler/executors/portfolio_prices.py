"""PortfolioPriceRefreshExecutor — APScheduler-bound tick body.

Thin wrapper around :func:`refresh_due_quotes`. The job is global (no
``user_id``) so APScheduler sees a single registered schedule; the base
executor's notification path is naturally skipped because notifications
are user-scoped.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

from openlia.llm.runtime.cancellation import CancellationToken

from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    SessionFactory,
)
from openlia_server.scheduler.registry import JobType
from openlia_server.services.portfolio_quote_refresh import (
    QuoteProvider,
    refresh_due_quotes,
)


class PortfolioPriceRefreshExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.PORTFOLIO_PRICE_REFRESH

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        provider: QuoteProvider,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        min_cadence_seconds: int | None = None,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._provider = provider
        self._clock = clock
        # ``None`` → use per-ticker floor cadence (scheduler_union). Tests
        # override this to force a deterministic threshold.
        self._min_cadence_seconds = min_cadence_seconds

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        now = self._clock()
        # The intraday cron registers itself with schedule_id="intraday" so we
        # can bypass the cadence floor for sub-hour fires whose whole purpose
        # is dense intraday rows. Top-of-hour / post-close / wake-up fires
        # pass schedule_id=None and keep cadence semantics.
        ignore_cadence = schedule_id == "intraday"
        with self._session_factory() as session:
            result = refresh_due_quotes(
                session,
                provider=self._provider,
                now_utc=now,
                min_cadence_seconds=self._min_cadence_seconds,
                ignore_cadence=ignore_cadence,
            )
        return JobOutcome(
            result_summary={
                "fetched": result.fetched,
                "skipped_fresh": result.skipped_fresh,
                "skipped_market_closed": result.skipped_market_closed,
                "failed": result.failed,
            },
            notifications=[],
        )


def production_executor(
    *,
    session_factory: SessionFactory,
    financial_adapter_provider: Callable[[], Any],
) -> PortfolioPriceRefreshExecutor:
    """Build the executor against the running app's financial_adapter.

    ``financial_adapter_provider`` is a callable returning the live adapter
    (typically ``lambda: app.state.financial_adapter``) so the executor
    picks up adapter swaps at runtime without a restart.
    """
    return PortfolioPriceRefreshExecutor(
        session_factory=session_factory,
        provider=_AdapterQuoteProvider(financial_adapter_provider),
    )


class _AdapterQuoteProvider:
    """Adapt the Plan 3 async ProviderAdapter to QuoteProvider's sync contract."""

    def __init__(self, adapter_provider: Callable[[], Any]) -> None:
        self._adapter_provider = adapter_provider

    def fetch_quote(self, ticker: str) -> dict | None:
        import asyncio
        import concurrent.futures

        from openlia_server.services.portfolio_prices import _coerce_price

        adapter = self._adapter_provider()
        if adapter is None:
            return None
        # APScheduler fires this from inside its own running event loop, so
        # a bare ``asyncio.run`` raises ``RuntimeError: asyncio.run() cannot be
        # called from a running event loop`` and the whole tick silently
        # returns None for every ticker. Detect that case and dispatch the
        # coroutine onto a worker thread that owns a fresh loop.
        def _run() -> Any:
            return asyncio.run(adapter.fetch("stock_quote", {"ticker": ticker.upper()}))

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                result = _run()
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(_run).result()
        except Exception:
            return None
        payload = getattr(result, "payload", None)
        price = _coerce_price(payload)
        if price is None:
            return None

        # EODHD shape: {"close": 150, "previousClose": 148, "open": ..., ...}.
        raw = payload if isinstance(payload, dict) else {}
        return {
            "last_price": price,
            "previous_close": _coerce_price(raw.get("previousClose")),
            "day_open": _coerce_price(raw.get("open")),
            "day_high": _coerce_price(raw.get("high")),
            "day_low": _coerce_price(raw.get("low")),
            "volume": int(raw["volume"])
            if "volume" in raw and raw["volume"] not in (None, "", "NA")
            else None,
            "currency": raw.get("currency"),
            "quote_at": None,
            "source": "eodhd",
        }
