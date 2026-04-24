"""HTTP tests for /departments/retail_sentiment/*."""

from __future__ import annotations

import pytest
from openlia_server.services.rs_runner import RsRunner

from ._rs_fakes import FakeRsDataProvider


@pytest.fixture
def rs_client(company_client, auth_user):
    from openlia_server.db import session as session_mod

    provider = FakeRsDataProvider.with_default_posts("AAPL")
    company_client.app.state.rs_data_provider = provider
    company_client.app.state.rs_runner = RsRunner(
        session_factory=session_mod.SessionLocal,
        data_provider=provider,
    )
    return company_client


def test_dashboard_requires_auth(company_client):
    r = company_client.get("/departments/retail_sentiment/dashboard")
    assert r.status_code == 401


def test_get_config_creates_default(rs_client):
    r = rs_client.get("/departments/retail_sentiment/config")
    assert r.status_code == 200
    body = r.json()
    assert body["active_tab"] == "overview"
    assert body["refresh_interval_minutes"] == 60


def test_put_config_persists(rs_client):
    r = rs_client.put(
        "/departments/retail_sentiment/config",
        json={"active_tab": "per_stock", "refresh_interval_minutes": 30},
    )
    assert r.status_code == 200
    assert r.json()["active_tab"] == "per_stock"
    reread = rs_client.get("/departments/retail_sentiment/config").json()
    assert reread["refresh_interval_minutes"] == 30


def test_put_config_rejects_too_small_interval(rs_client):
    r = rs_client.put(
        "/departments/retail_sentiment/config",
        json={"refresh_interval_minutes": 1},
    )
    assert r.status_code == 400


def test_run_creates_snapshot(rs_client):
    r = rs_client.post("/departments/retail_sentiment/run", json={"tickers": ["AAPL"]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["snapshots"]) == 1
    snap = body["snapshots"][0]
    assert snap["ticker"] == "AAPL"
    assert snap["buzz_volume"] == 8.0  # 5 social + 3 news


def test_run_requires_tickers(rs_client):
    r = rs_client.post("/departments/retail_sentiment/run", json={"tickers": []})
    assert r.status_code == 400


def test_dashboard_returns_latest_snapshots_after_run(rs_client):
    rs_client.post("/departments/retail_sentiment/run", json={"tickers": ["AAPL"]})
    r = rs_client.get("/departments/retail_sentiment/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert "AAPL" in body["tickers"]
    assert any(s["ticker"] == "AAPL" for s in body["snapshots"])


def test_stock_sentiment_404_when_missing(rs_client):
    r = rs_client.get("/departments/retail_sentiment/stocks/UNKNOWN/sentiment")
    assert r.status_code == 404


def test_stock_sentiment_after_run(rs_client):
    rs_client.post("/departments/retail_sentiment/run", json={"tickers": ["AAPL"]})
    r = rs_client.get("/departments/retail_sentiment/stocks/AAPL/sentiment")
    assert r.status_code == 200
    body = r.json()
    assert body["latest"]["ticker"] == "AAPL"


def test_history_returns_list(rs_client):
    rs_client.post("/departments/retail_sentiment/run", json={"tickers": ["AAPL"]})
    r = rs_client.get("/departments/retail_sentiment/dashboard/history?ticker=AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert isinstance(body["snapshots"], list)


def test_spikes_empty_without_history(rs_client):
    r = rs_client.get("/departments/retail_sentiment/spikes")
    assert r.status_code == 200
    assert r.json() == {"spikes": []}
