"""Phase 1: market_hours service.

Hardcoded NYSE/NASDAQ + TWSE sessions. No holiday calendar in v1 — that's an
accepted limitation per the design spec. Tickers outside these markets fall
back to "always open" so the scheduler still fetches them.
"""

from __future__ import annotations

from datetime import UTC, datetime


def test_us_ticker_open_during_us_session() -> None:
    from openlia_server.services.market_hours import is_market_open

    # Tuesday 2026-05-12, 14:30 UTC == 10:30am ET (during NYSE session)
    weekday_open = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    assert is_market_open("AAPL", weekday_open) is True


def test_us_ticker_closed_on_weekend() -> None:
    from openlia_server.services.market_hours import is_market_open

    # Saturday 2026-05-16, 14:30 UTC
    saturday = datetime(2026, 5, 16, 14, 30, tzinfo=UTC)
    assert is_market_open("AAPL", saturday) is False


def test_us_ticker_closed_before_open() -> None:
    from openlia_server.services.market_hours import is_market_open

    # Tuesday 2026-05-12, 13:00 UTC == 9:00am ET (before 9:30 open)
    early = datetime(2026, 5, 12, 13, 0, tzinfo=UTC)
    assert is_market_open("AAPL", early) is False


def test_us_ticker_closed_after_close() -> None:
    from openlia_server.services.market_hours import is_market_open

    # Tuesday 2026-05-12, 20:30 UTC == 4:30pm ET (after 4pm close)
    late = datetime(2026, 5, 12, 20, 30, tzinfo=UTC)
    assert is_market_open("AAPL", late) is False


def test_twse_ticker_open_during_taipei_session() -> None:
    from openlia_server.services.market_hours import is_market_open

    # Tuesday 2026-05-12, 04:30 UTC == 12:30pm Taipei (during TWSE session)
    open_twse = datetime(2026, 5, 12, 4, 30, tzinfo=UTC)
    assert is_market_open("2330.TW", open_twse) is True


def test_twse_ticker_closed_after_local_close() -> None:
    from openlia_server.services.market_hours import is_market_open

    # Tuesday 2026-05-12, 06:00 UTC == 2:00pm Taipei (after 1:30pm close)
    after = datetime(2026, 5, 12, 6, 0, tzinfo=UTC)
    assert is_market_open("2330.TW", after) is False


def test_unknown_market_falls_back_to_always_open() -> None:
    from openlia_server.services.market_hours import is_market_open

    # An unknown suffix (.LSE etc.) — fall back to "always open" so the
    # scheduler still fetches at user cadence.
    saturday = datetime(2026, 5, 16, 14, 30, tzinfo=UTC)
    assert is_market_open("RDSB.LSE", saturday) is True


def test_us_ticker_open_at_session_boundaries() -> None:
    """NYSE session boundaries are inclusive on open, exclusive on close."""
    from openlia_server.services.market_hours import is_market_open

    # 9:30am ET == 13:30 UTC
    boundary_open = datetime(2026, 5, 12, 13, 30, tzinfo=UTC)
    # 4:00pm ET == 20:00 UTC
    boundary_close = datetime(2026, 5, 12, 20, 0, tzinfo=UTC)
    assert is_market_open("AAPL", boundary_open) is True
    assert is_market_open("AAPL", boundary_close) is False
