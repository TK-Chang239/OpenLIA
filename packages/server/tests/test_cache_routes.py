"""Tests for cache admin API (X5): GET /api/cache/stats + DELETE /api/cache/documents."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia_server.db.models.auth import User
from openlia_server.db.models.cache import CachedDocument


def _make_doc(cache_key: str, ticker: str | None = None, bytes_size: int = 10) -> CachedDocument:
    now = datetime.now(UTC)
    return CachedDocument(
        cache_key=cache_key,
        source="eodhd",
        document_id=cache_key,
        ticker=ticker,
        fiscal_period=None,
        content_text="x" * bytes_size,
        raw_metadata={},
        original_retrieved_at=now,
        cached_at=now,
        bytes_size=bytes_size,
    )


@pytest.fixture()
def cache_client(db_session_factory):
    from openlia_server.routes.cache import build_cache_router

    # The router is admin-gated. In personal mode the gate resolves to the
    # synthetic `local` user, so seed it so the admin dependency succeeds.
    with db_session_factory() as s:
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()

    app = FastAPI()
    app.include_router(
        build_cache_router(db_session_factory=db_session_factory, mode="personal"),
        prefix="/api",
    )
    return TestClient(app)


@pytest.fixture()
def company_cache_client(db_session_factory):
    """Company-mode client with no session cookie — used to prove the gate."""
    from openlia_server.routes.cache import build_cache_router

    app = FastAPI()
    app.include_router(
        build_cache_router(db_session_factory=db_session_factory, mode="company"),
        prefix="/api",
    )
    return TestClient(app)


def test_cache_routes_require_auth_in_company_mode(company_cache_client):
    # P0-1 regression: the destructive DELETE and stats must never be reachable
    # unauthenticated. Company mode with no cookie must reject both.
    assert company_cache_client.get("/api/cache/stats").status_code in (401, 403)
    assert company_cache_client.delete("/api/cache/documents").status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/cache/stats
# ---------------------------------------------------------------------------


def test_cache_stats_empty(cache_client):
    resp = cache_client.get("/api/cache/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"total_entries": 0, "total_bytes": 0}


def test_cache_stats_after_insert(cache_client, db_session):
    doc = _make_doc("eodhd:get_financials:AAPL:2024Q1", ticker="AAPL", bytes_size=42)
    db_session.add(doc)
    db_session.commit()

    resp = cache_client.get("/api/cache/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_entries"] == 1
    assert body["total_bytes"] == 42


# ---------------------------------------------------------------------------
# DELETE /api/cache/documents
# ---------------------------------------------------------------------------


def test_clear_cache_for_ticker(cache_client, db_session):
    db_session.add(_make_doc("key:NVDA:1", ticker="NVDA", bytes_size=5))
    db_session.add(_make_doc("key:NVDA:2", ticker="NVDA", bytes_size=5))
    db_session.add(_make_doc("key:AAPL:1", ticker="AAPL", bytes_size=5))
    db_session.commit()

    resp = cache_client.delete("/api/cache/documents?ticker=NVDA")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}

    # AAPL row must remain
    remaining = db_session.query(CachedDocument).all()
    assert len(remaining) == 1
    assert remaining[0].ticker == "AAPL"


def test_clear_all_cache(cache_client, db_session):
    for i in range(3):
        db_session.add(_make_doc(f"key:ALL:{i}", ticker="MSFT"))
    db_session.commit()

    resp = cache_client.delete("/api/cache/documents")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 3}

    assert db_session.query(CachedDocument).count() == 0
