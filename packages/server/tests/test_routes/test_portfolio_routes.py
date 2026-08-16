"""Portfolio route wire tests — auth gating + CRUD + analytics + CSV."""

from __future__ import annotations


def test_list_holdings_requires_auth(client) -> None:
    resp = client.get("/portfolio/holdings")
    assert resp.status_code in (401, 403)


def test_crud_round_trip(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)

    # Create
    r = client.post(
        "/portfolio/holdings",
        json={"ticker": "aapl", "shares": "10", "cost_basis": "150", "currency": "USD"},
    )
    assert r.status_code == 201, r.text
    holding = r.json()
    assert holding["ticker"] == "AAPL"
    assert holding["currency"] == "USD"
    holding_id = holding["id"]

    # List
    r = client.get("/portfolio/holdings")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"

    # Duplicate 409
    r = client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "5", "currency": "USD"},
    )
    assert r.status_code == 409

    # Patch shares
    r = client.patch(f"/portfolio/holdings/{holding_id}", json={"shares": "25"})
    assert r.status_code == 200
    assert r.json()["shares"].startswith("25")

    # Delete
    r = client.delete(f"/portfolio/holdings/{holding_id}")
    assert r.status_code == 204

    # Delete again -> 404
    r = client.delete(f"/portfolio/holdings/{holding_id}")
    assert r.status_code == 404


def test_per_user_scoping(client, user_factory, login_as) -> None:
    u1 = user_factory()
    u2 = user_factory()
    login_as(u1)
    client.post("/portfolio/holdings", json={"ticker": "AAPL"})
    login_as(u2)
    r = client.get("/portfolio/holdings")
    assert r.json() == []


def test_analytics_empty_returns_zeros(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.get("/portfolio/analytics")
    assert r.status_code == 200
    body = r.json()
    assert body["total_market_value"] == "0.0000"
    assert body["positions"] == []


def test_refresh_prices_then_cooldown(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "10", "cost_basis": "100"},
    )
    r = client.post("/portfolio/refresh-prices")
    assert r.status_code == 200
    # Second call within cooldown -> 429
    r = client.post("/portfolio/refresh-prices")
    assert r.status_code == 429


def test_csv_export_roundtrip(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "10", "cost_basis": "150", "currency": "USD"},
    )
    r = client.get("/portfolio/export-csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "AAPL" in r.text


def test_csv_import(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    csv_text = "ticker,shares,cost_basis,currency,notes\nNVDA,2,400,USD,\n"
    r = client.post("/portfolio/import-csv", json={"text": csv_text})
    assert r.status_code == 200
    body = r.json()
    assert len(body["created"]) == 1
    assert body["created"][0]["ticker"] == "NVDA"


def test_search_uses_adapter(client, user_factory, login_as) -> None:
    """Search resolves over the configured financial adapter via company_profile."""

    class _ToolResult:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

    class _FakeAdapter:
        async def fetch(self, capability: str, params: dict) -> _ToolResult:
            assert capability == "company_profile"
            # Assert the caller kwarg name matches the eodhd company_profile
            # binding (ParamBinding to_arg="ticker"). Passing "symbol" here is
            # dropped silently by the dispatcher -> dead search (audit 1.A.1).
            assert params == {"ticker": "AAPL"}
            return _ToolResult(
                {"General": {"Code": "AAPL", "Name": "Apple Inc.", "Exchange": "NASDAQ"}}
            )

    client.app.state.financial_adapter = _FakeAdapter()
    try:
        u = user_factory()
        login_as(u)
        r = client.get("/portfolio/search?q=aapl")
        assert r.status_code == 200
        body = r.json()
        assert body["results"] == [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "already_added": False,
            }
        ]
    finally:
        client.app.state.financial_adapter = None


def test_search_empty_query_returns_empty(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.get("/portfolio/search?q=")
    assert r.status_code == 200
    assert r.json() == {"results": []}


def test_search_marks_already_added(client, user_factory, login_as) -> None:
    class _ToolResult:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

    class _FakeAdapter:
        async def fetch(self, capability: str, params: dict) -> _ToolResult:
            return _ToolResult({"General": {"Code": "AAPL", "Name": "Apple Inc."}})

    client.app.state.financial_adapter = _FakeAdapter()
    try:
        u = user_factory()
        login_as(u)
        client.post("/portfolio/holdings", json={"ticker": "AAPL", "shares": "1"})
        r = client.get("/portfolio/search?q=aapl")
        body = r.json()
        assert body["results"][0]["already_added"] is True
    finally:
        client.app.state.financial_adapter = None


def test_search_adapter_error_returns_empty(client, user_factory, login_as) -> None:
    class _RaisingAdapter:
        async def fetch(self, capability: str, params: dict):
            raise RuntimeError("boom")

    client.app.state.financial_adapter = _RaisingAdapter()
    try:
        u = user_factory()
        login_as(u)
        r = client.get("/portfolio/search?q=zzz")
        assert r.status_code == 200
        assert r.json() == {"results": []}
    finally:
        client.app.state.financial_adapter = None


def test_groups_create_list_rename_delete(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    # Create
    r = client.post("/portfolio/groups", json={"name": "Tech"})
    assert r.status_code == 201
    assert "Tech" in r.json()["groups"]
    # List
    r = client.get("/portfolio/groups")
    assert r.status_code == 200
    assert "Tech" in r.json()["groups"]
    # Rename
    r = client.patch("/portfolio/groups/Tech", json={"new_name": "Megacap"})
    assert r.status_code == 200
    assert "Megacap" in r.json()["groups"]
    # Delete
    r = client.delete("/portfolio/groups/Megacap")
    assert r.status_code == 200
    assert "Megacap" not in r.json()["groups"]


def test_groups_reorder(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    client.post("/portfolio/groups", json={"name": "A"})
    client.post("/portfolio/groups", json={"name": "B"})
    r = client.post("/portfolio/groups/reorder", json={"order": ["B", "A"]})
    assert r.status_code == 200
    assert r.json()["groups"] == ["B", "A"]


def test_groups_rename_unknown_returns_404(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.patch("/portfolio/groups/Nope", json={"new_name": "X"})
    assert r.status_code == 404


def test_groups_endpoints_require_auth(client) -> None:
    r = client.get("/portfolio/groups")
    assert r.status_code in (401, 403)


# ----------------------------------------------------------------------
# Phase 1 (portfolio live data) — analytics reads from portfolio_quotes
# ----------------------------------------------------------------------


def test_analytics_reads_from_portfolio_quotes_table(client, user_factory, login_as) -> None:
    """After upserting a row into portfolio_quotes, /analytics reflects the
    last_price and surfaces last_quote_at."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from openlia_server.db import session as session_mod
    from openlia_server.services import portfolio_quotes as quotes_svc

    u = user_factory()
    login_as(u)
    client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "10", "cost_basis": "150"},
    )

    quote_at = datetime(2026, 5, 11, 1, 30, tzinfo=UTC)
    with session_mod.SessionLocal() as s:
        quotes_svc.upsert_quote(
            s,
            ticker="AAPL",
            last_price=Decimal("200"),
            previous_close=Decimal("195"),
            day_open=Decimal("196"),
            day_high=Decimal("202"),
            day_low=Decimal("195.5"),
            volume=42,
            currency="USD",
            quote_at=quote_at,
            fetched_at=quote_at,
            source="eodhd",
        )

    r = client.get("/portfolio/analytics")
    assert r.status_code == 200
    body = r.json()
    assert body["last_quote_at"] is not None
    assert "2026-05-11" in body["last_quote_at"]
    # 10 * 200 = 2000 market value
    assert body["total_market_value"].startswith("2000")
    # Position last_price reflects the DB row, not the legacy in-memory cache.
    pos = body["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert Decimal(pos["last_price"]) == Decimal("200")


def test_analytics_last_quote_at_null_when_no_quotes(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    client.post("/portfolio/holdings", json={"ticker": "ZZZZ"})
    r = client.get("/portfolio/analytics")
    assert r.status_code == 200
    body = r.json()
    assert body["last_quote_at"] is None


def test_refresh_prices_persists_to_portfolio_quotes(client, user_factory, login_as) -> None:
    """Manual refresh must populate the portfolio_quotes table so subsequent
    /analytics calls reflect the just-fetched prices."""
    from decimal import Decimal

    from openlia_server.db import session as session_mod
    from openlia_server.services import portfolio_quotes as quotes_svc

    class _ToolResult:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

    class _FakeAdapter:
        async def fetch(self, capability: str, params: dict) -> _ToolResult:
            assert capability == "stock_quote"
            return _ToolResult({"close": "321.50"})

    client.app.state.financial_adapter = _FakeAdapter()
    try:
        u = user_factory()
        login_as(u)
        client.post(
            "/portfolio/holdings",
            json={"ticker": "MSFT", "shares": "5"},
        )

        r = client.post("/portfolio/refresh-prices")
        assert r.status_code == 200

        with session_mod.SessionLocal() as s:
            row = quotes_svc.get_quote(s, ticker="MSFT")

        assert row is not None
        assert row.last_price == Decimal("321.50")
        assert row.source != ""
    finally:
        client.app.state.financial_adapter = None


def test_create_holding_requires_shares(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "currency": "USD"},
    )
    assert r.status_code == 400
    assert "shares" in r.json()["detail"].lower()


def test_create_holding_with_added_at_date_market_local_midnight(
    client, user_factory, login_as
) -> None:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioHolding

    u = user_factory()
    login_as(u)
    r = client.post(
        "/portfolio/holdings?market=us",
        json={
            "ticker": "AAPL",
            "shares": "10",
            "currency": "USD",
            "added_at_date": "2026-01-15",
        },
    )
    assert r.status_code == 201, r.text

    expected = datetime(2026, 1, 15, 0, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(UTC)
    with session_mod.SessionLocal() as s:
        row = s.query(PortfolioHolding).filter_by(user_id=u.id, ticker="AAPL").one()
    assert row.added_at == expected


def test_create_holding_with_added_at_date_tw_market_timezone(
    client, user_factory, login_as
) -> None:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioHolding

    u = user_factory()
    login_as(u)
    r = client.post(
        "/portfolio/holdings?market=tw",
        json={
            "ticker": "2330.TW",
            "shares": "100",
            "currency": "TWD",
            "added_at_date": "2026-02-20",
        },
    )
    assert r.status_code == 201, r.text

    expected = datetime(2026, 2, 20, 0, 0, tzinfo=ZoneInfo("Asia/Taipei")).astimezone(UTC)
    with session_mod.SessionLocal() as s:
        row = s.query(PortfolioHolding).filter_by(user_id=u.id, ticker="2330.TW").one()
    assert row.added_at == expected


def test_create_holding_rejects_future_added_at(client, user_factory, login_as) -> None:
    from datetime import UTC, datetime, timedelta

    u = user_factory()
    login_as(u)
    future = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()
    r = client.post(
        "/portfolio/holdings?market=us",
        json={
            "ticker": "AAPL",
            "shares": "10",
            "added_at_date": future,
        },
    )
    assert r.status_code == 400
    assert "future" in r.json()["detail"].lower()


def test_create_holding_rejects_invalid_added_at_format(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.post(
        "/portfolio/holdings?market=us",
        json={
            "ticker": "AAPL",
            "shares": "10",
            "added_at_date": "01/15/2026",
        },
    )
    assert r.status_code == 400


def test_analytics_surfaces_day_change_from_portfolio_quotes(
    client, user_factory, login_as
) -> None:
    """When portfolio_quotes carries previous_close, /analytics must surface
    per-position previous_close, day_change_abs (per-share x shares), and
    day_change_pct so the HoldingsTable can render a DAY column."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from openlia_server.db import session as session_mod
    from openlia_server.services import portfolio_quotes as quotes_svc

    u = user_factory()
    login_as(u)
    client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "10", "cost_basis": "150"},
    )

    quote_at = datetime(2026, 5, 11, 1, 30, tzinfo=UTC)
    with session_mod.SessionLocal() as s:
        quotes_svc.upsert_quote(
            s,
            ticker="AAPL",
            last_price=Decimal("200"),
            previous_close=Decimal("195"),
            day_open=Decimal("196"),
            day_high=Decimal("202"),
            day_low=Decimal("195.5"),
            volume=42,
            currency="USD",
            quote_at=quote_at,
            fetched_at=quote_at,
            source="eodhd",
        )

    r = client.get("/portfolio/analytics")
    assert r.status_code == 200
    pos = r.json()["positions"][0]
    assert Decimal(pos["previous_close"]) == Decimal("195")
    # (200 - 195) * 10 shares = 50
    assert Decimal(pos["day_change_abs"]) == Decimal("50")
    # (200 - 195) / 195 ≈ 0.025641
    pct = Decimal(pos["day_change_pct"])
    assert Decimal("0.0256") < pct < Decimal("0.0257")


def test_analytics_day_change_falls_back_to_daily_history(client, user_factory, login_as) -> None:
    """When portfolio_quotes.previous_close is null but portfolio_quote_daily
    has at least one row strictly before today, the second-most-recent close
    serves as the previous-day baseline. Today's last_price is taken from
    portfolio_quotes."""
    from datetime import UTC, date, datetime, timedelta
    from decimal import Decimal

    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioQuoteDaily
    from openlia_server.services import portfolio_quotes as quotes_svc

    u = user_factory()
    login_as(u)
    client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "10", "cost_basis": "150"},
    )

    now = datetime.now(UTC)
    with session_mod.SessionLocal() as s:
        quotes_svc.upsert_quote(
            s,
            ticker="AAPL",
            last_price=Decimal("110"),
            previous_close=None,
            day_open=None,
            day_high=None,
            day_low=None,
            volume=None,
            currency="USD",
            quote_at=now,
            fetched_at=now,
            source="fake",
        )
        today: date = now.date()
        s.add(
            PortfolioQuoteDaily(
                ticker="AAPL",
                trade_date=today - timedelta(days=2),
                close=Decimal("100"),
            )
        )
        s.add(
            PortfolioQuoteDaily(
                ticker="AAPL",
                trade_date=today - timedelta(days=1),
                close=Decimal("105"),
            )
        )
        s.commit()

    r = client.get("/portfolio/analytics")
    assert r.status_code == 200
    pos = r.json()["positions"][0]
    assert Decimal(pos["previous_close"]) == Decimal("105")
    assert Decimal(pos["day_change_abs"]) == Decimal("50")  # (110-105)*10
    pct = Decimal(pos["day_change_pct"])
    assert Decimal("0.0476") < pct < Decimal("0.0477")


def test_analytics_day_change_null_when_no_baseline(client, user_factory, login_as) -> None:
    """Without any previous_close source, day_change fields are null."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from openlia_server.db import session as session_mod
    from openlia_server.services import portfolio_quotes as quotes_svc

    u = user_factory()
    login_as(u)
    client.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "10", "cost_basis": "150"},
    )

    now = datetime.now(UTC)
    with session_mod.SessionLocal() as s:
        quotes_svc.upsert_quote(
            s,
            ticker="AAPL",
            last_price=Decimal("110"),
            previous_close=None,
            day_open=None,
            day_high=None,
            day_low=None,
            volume=None,
            currency="USD",
            quote_at=now,
            fetched_at=now,
            source="fake",
        )

    r = client.get("/portfolio/analytics")
    assert r.status_code == 200
    pos = r.json()["positions"][0]
    assert pos["previous_close"] is None
    assert pos["day_change_abs"] is None
    assert pos["day_change_pct"] is None
