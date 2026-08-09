"""Integration tests for GET /markets/indices."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestMarketsIndices:
    def test_available_false_without_key(self, personal_client: TestClient, monkeypatch):
        # No env key and no eodhd connector -> the strip should show its
        # connect-EODHD empty state, not an error.
        monkeypatch.delenv("EODHD_API_KEY", raising=False)
        resp = personal_client.get("/markets/indices")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["indices"] == []

    def test_returns_basket_when_key_present(self, personal_client: TestClient, monkeypatch):
        from openlia_server.services import markets_quotes

        monkeypatch.setenv("EODHD_API_KEY", "test-key")
        fixed = [
            {
                "symbol": "GSPC.INDX",
                "label": "S&P 500",
                "value": 7757.64,
                "previous_close": 7709.96,
                "change_abs": 47.68,
                "change_pct": 0.62,
            }
        ]
        monkeypatch.setattr(markets_quotes, "fetch_indices", lambda api_key: fixed)

        resp = personal_client.get("/markets/indices")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["indices"] == fixed

    def test_fetch_error_degrades_to_empty(self, personal_client: TestClient, monkeypatch):
        from openlia_server.services import markets_quotes

        monkeypatch.setenv("EODHD_API_KEY", "test-key")

        def boom(api_key):
            raise RuntimeError("eodhd down")

        monkeypatch.setattr(markets_quotes, "fetch_indices", boom)

        resp = personal_client.get("/markets/indices")
        assert resp.status_code == 200
        body = resp.json()
        # Key exists (available) but the upstream failed -> empty, no 500.
        assert body["available"] is True
        assert body["indices"] == []
