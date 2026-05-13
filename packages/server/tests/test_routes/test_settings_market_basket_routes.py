"""Routes for the default market-snapshot basket (fix-chats).

GET /settings/preferences/market-basket  → current basket (defaults if unset)
PUT /settings/preferences/market-basket  → set basket (validated)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

DEFAULT_BASKET = {
    "tape": ["SPY", "QQQ", "DIA", "IWM"],
    "risk": ["VIX", "HYG", "TLT"],
    "macro": ["DXY", "GLD", "USO"],
    "crypto": ["BTC"],
}


def test_get_returns_default_when_unset(company_client: TestClient, auth_user) -> None:
    resp = company_client.get("/settings/preferences/market-basket")
    assert resp.status_code == 200
    assert resp.json() == DEFAULT_BASKET


def test_put_persists_and_normalizes_basket(company_client: TestClient, auth_user) -> None:
    payload = {
        "tape": ["spy", "qqq"],
        "risk": [" vix "],
        "macro": ["dxy"],
        "crypto": ["BTC", "ETH"],
    }
    resp = company_client.put("/settings/preferences/market-basket", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["tape"] == ["SPY", "QQQ"]
    assert body["risk"] == ["VIX"]
    assert body["macro"] == ["DXY"]
    assert body["crypto"] == ["BTC", "ETH"]
    # Persisted on next GET
    refetch = company_client.get("/settings/preferences/market-basket").json()
    assert refetch == body


def test_put_rejects_missing_section(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/preferences/market-basket",
        json={"tape": ["SPY"], "risk": ["VIX"], "macro": ["DXY"]},
    )
    assert resp.status_code == 422


def test_put_rejects_invalid_ticker(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/preferences/market-basket",
        json={
            "tape": ["spy with spaces"],
            "risk": ["VIX"],
            "macro": ["DXY"],
            "crypto": ["BTC"],
        },
    )
    assert resp.status_code == 422


def test_put_rejects_empty_section(company_client: TestClient, auth_user) -> None:
    resp = company_client.put(
        "/settings/preferences/market-basket",
        json={
            "tape": [],
            "risk": ["VIX"],
            "macro": ["DXY"],
            "crypto": ["BTC"],
        },
    )
    assert resp.status_code == 422


def test_put_then_get_round_trip_persists(company_client: TestClient, auth_user) -> None:
    """End-to-end persistence check."""
    custom = {
        "tape": ["IVV", "VTI"],
        "risk": ["UVXY"],
        "macro": ["UUP"],
        "crypto": ["BTC", "ETH", "SOL"],
    }
    company_client.put("/settings/preferences/market-basket", json=custom)
    assert company_client.get("/settings/preferences/market-basket").json() == custom
