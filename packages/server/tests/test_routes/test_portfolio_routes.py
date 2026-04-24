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


def test_search_echoes_query(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.get("/portfolio/search?q=aapl")
    assert r.status_code == 200
    assert r.json() == {"results": [{"ticker": "AAPL", "name": None}]}
