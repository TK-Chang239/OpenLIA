"""Phase 1: PortfolioPriceRefreshExecutor — APScheduler-bound wrapper around
refresh_due_quotes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

# Register every ORM model on Base.metadata *before* the scheduler conftest's
# in-memory engine fixture calls Base.metadata.create_all(eng), otherwise the
# users/portfolio_holdings tables don't exist when we insert below.
import openlia_server.db.models.register_all  # noqa: F401
import pytest


class _RecordingProvider:
    def __init__(self, prices: dict[str, Decimal]) -> None:
        self.prices = prices
        self.called: list[str] = []

    def fetch_quote(self, ticker: str) -> dict | None:
        self.called.append(ticker)
        if ticker not in self.prices:
            return None
        return {
            "last_price": self.prices[ticker],
            "previous_close": None,
            "day_open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "currency": "USD",
            "quote_at": None,
            "source": "fake",
        }


def _seed_holding(db_session, ticker: str) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import PortfolioHolding

    if db_session.get(User, "u-port-exec") is None:
        db_session.add(
            User(
                id="u-port-exec",
                email="u@example.com",
                display_name="u",
                password_hash=None,
                is_admin=False,
                is_disabled=False,
            )
        )
    db_session.add(PortfolioHolding(id=f"h-{ticker}", user_id="u-port-exec", ticker=ticker))
    db_session.commit()


@pytest.mark.asyncio
async def test_executor_runs_refresh_and_writes_quotes(db_session, session_factory) -> None:
    from openlia_server.scheduler.executors.portfolio_prices import (
        PortfolioPriceRefreshExecutor,
    )
    from openlia_server.scheduler.registry import JobType
    from openlia_server.services import portfolio_quotes as quotes_svc

    _seed_holding(db_session, "AAPL")
    provider = _RecordingProvider({"AAPL": Decimal("150")})
    # Tuesday during US market hours.
    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    executor = PortfolioPriceRefreshExecutor(
        session_factory=session_factory,
        provider=provider,
        clock=lambda: now,
        min_cadence_seconds=3600,
    )
    assert executor.job_type is JobType.PORTFOLIO_PRICE_REFRESH

    await executor.execute(user_id=None, schedule_id=None)

    with session_factory() as s:
        row = quotes_svc.get_quote(s, ticker="AAPL")
    assert row is not None
    assert row.last_price == Decimal("150")
    assert provider.called == ["AAPL"]


@pytest.mark.asyncio
async def test_executor_records_job_run(db_session, session_factory) -> None:
    """A job_runs row should be opened on each fire so the admin UI can
    surface refresh history just like other scheduled jobs."""
    from openlia_server.db.models.scheduler import JobRun
    from openlia_server.scheduler.executors.portfolio_prices import (
        PortfolioPriceRefreshExecutor,
    )
    from sqlalchemy import select

    _seed_holding(db_session, "AAPL")
    provider = _RecordingProvider({"AAPL": Decimal("150")})
    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    executor = PortfolioPriceRefreshExecutor(
        session_factory=session_factory,
        provider=provider,
        clock=lambda: now,
        min_cadence_seconds=3600,
    )

    await executor.execute(user_id=None, schedule_id=None)

    with session_factory() as s:
        runs = (
            s.execute(select(JobRun).where(JobRun.job_type == "portfolio_price_refresh"))
            .scalars()
            .all()
        )
    assert len(runs) == 1
    assert runs[0].status == "completed"


@pytest.mark.asyncio
async def test_intraday_schedule_id_honors_cadence_floor(db_session, session_factory) -> None:
    """The */15 sub-hour cron fires every 15 minutes but honors the per-ticker
    cadence floor. A user on an hourly floor skips-fresh on sub-hour fires that
    land inside the window; only users whose floor is <= the fire spacing (the
    15min cadence) accumulate intraday rows on every fire."""
    from datetime import timedelta

    from openlia_server.db.models.content import PortfolioQuoteIntraday
    from openlia_server.scheduler.executors.portfolio_prices import (
        PortfolioPriceRefreshExecutor,
    )
    from openlia_server.services import portfolio_quotes as quotes_svc
    from sqlalchemy import select

    _seed_holding(db_session, "AAPL")
    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)  # Tue 10:30 ET, market open
    quotes_svc.upsert_quote(
        db_session,
        ticker="AAPL",
        last_price=Decimal("100"),
        previous_close=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        currency="USD",
        quote_at=now - timedelta(minutes=10),
        fetched_at=now - timedelta(minutes=10),
        source="fake",
    )
    provider = _RecordingProvider({"AAPL": Decimal("101")})
    executor = PortfolioPriceRefreshExecutor(
        session_factory=session_factory,
        provider=provider,
        clock=lambda: now,
        min_cadence_seconds=3600,
    )

    await executor.execute(user_id=None, schedule_id="intraday")

    assert provider.called == []
    with session_factory() as s:
        rows = (
            s.execute(select(PortfolioQuoteIntraday).where(PortfolioQuoteIntraday.ticker == "AAPL"))
            .scalars()
            .all()
        )
    assert rows == []


@pytest.mark.asyncio
async def test_adapter_quote_provider_works_inside_running_event_loop() -> None:
    """The production QuoteProvider wraps an async adapter. APScheduler fires
    jobs inside its own event loop, so the provider's adapter call must work
    when invoked from async context. A naive ``asyncio.run(adapter.fetch(...))``
    raises ``RuntimeError: asyncio.run() cannot be called from a running event
    loop`` and the wrapping ``except`` would silently return None — producing
    'failed' on every scheduled fire and zero intraday rows."""
    from openlia_server.scheduler.executors.portfolio_prices import (
        _AdapterQuoteProvider,
    )

    class _FakeResult:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

    class _FakeAsyncAdapter:
        async def fetch(self, capability: str, params: dict) -> _FakeResult:
            assert capability == "stock_quote"
            return _FakeResult({"close": "123.45", "previousClose": "120.00"})

    provider = _AdapterQuoteProvider(lambda: _FakeAsyncAdapter())
    # We are inside an async test, so the executor's runtime context matches
    # APScheduler's. If the provider mishandles this, fetch_quote returns None.
    result = provider.fetch_quote("AAPL")
    assert result is not None, (
        "fetch_quote returned None inside a running event loop — "
        "asyncio.run() is being called from async context"
    )
    assert str(result["last_price"]) == "123.45"
    assert str(result["previous_close"]) == "120.00"
