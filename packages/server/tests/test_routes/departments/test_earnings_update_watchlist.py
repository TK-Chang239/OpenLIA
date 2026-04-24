"""HTTP tests for /departments/earnings-update/watchlist."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class _FakeAdapter:
    lookup: dict | None

    def next_earnings(self, ticker: str) -> dict | None:
        return self.lookup


def _install_adapter(client, lookup: dict | None) -> None:
    client.app.state.earnings_adapter = _FakeAdapter(lookup=lookup)


def test_get_watchlist_empty(company_client, auth_user):
    _install_adapter(company_client, None)
    r = company_client.get("/departments/earnings-update/watchlist")
    assert r.status_code == 200
    assert r.json() == {"entries": []}


def test_add_and_list(company_client, auth_user):
    _install_adapter(
        company_client,
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "date": date(2026, 4, 25),
            "release_timing": "post_market",
        },
    )
    r = company_client.post(
        "/departments/earnings-update/watchlist",
        json={"ticker": "aapl"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["company_name"] == "Apple Inc."

    r = company_client.get("/departments/earnings-update/watchlist")
    assert r.status_code == 200
    assert len(r.json()["entries"]) == 1


def test_add_duplicate_returns_409(company_client, auth_user):
    _install_adapter(
        company_client,
        {"ticker": "AAPL", "company_name": "Apple Inc.", "date": None, "release_timing": None},
    )
    r = company_client.post(
        "/departments/earnings-update/watchlist", json={"ticker": "AAPL"}
    )
    assert r.status_code == 201
    r2 = company_client.post(
        "/departments/earnings-update/watchlist", json={"ticker": "AAPL"}
    )
    assert r2.status_code == 409


def test_add_unknown_ticker_returns_404(company_client, auth_user):
    _install_adapter(company_client, None)
    r = company_client.post(
        "/departments/earnings-update/watchlist", json={"ticker": "ZZZZ"}
    )
    assert r.status_code == 404


def test_delete_entry(company_client, auth_user):
    _install_adapter(
        company_client,
        {"ticker": "AAPL", "company_name": "Apple Inc.", "date": None, "release_timing": None},
    )
    post = company_client.post(
        "/departments/earnings-update/watchlist", json={"ticker": "AAPL"}
    )
    entry_id = post.json()["id"]
    r = company_client.delete(f"/departments/earnings-update/watchlist/{entry_id}")
    assert r.status_code == 204
    r2 = company_client.get("/departments/earnings-update/watchlist")
    assert r2.json()["entries"] == []


def test_delete_unknown_returns_404(company_client, auth_user):
    r = company_client.delete("/departments/earnings-update/watchlist/bogus")
    assert r.status_code == 404


def test_watchlist_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/earnings-update/watchlist")
    assert r.status_code == 401


def test_watchlist_is_user_scoped(company_client, auth_user, user_factory, login_as, client):
    # Seed adapter on the auth_user's client
    _install_adapter(
        company_client,
        {"ticker": "AAPL", "company_name": "Apple Inc.", "date": None, "release_timing": None},
    )
    company_client.post(
        "/departments/earnings-update/watchlist", json={"ticker": "AAPL"}
    )
    # Different user via `client` fixture
    other = user_factory()
    login_as(other)
    client.app.state.earnings_adapter = _FakeAdapter(
        lookup={
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "date": None,
            "release_timing": None,
        }
    )
    r = client.get("/departments/earnings-update/watchlist")
    assert r.status_code == 200
    assert r.json()["entries"] == []
