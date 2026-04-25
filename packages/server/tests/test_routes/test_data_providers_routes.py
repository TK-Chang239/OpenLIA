"""Route tests for /settings/data-providers/*.

All routes require admin. In personal mode the synthetic `local` user is
admin, so tests build the app with OPENLIA_MODE=personal and do NOT send a
session cookie. In company mode they build the app with OPENLIA_MODE=company
and send a valid admin session.
"""

from datetime import UTC, datetime

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from openlia_server.app import create_app


@pytest.fixture
def personal_client(db_session, monkeypatch):
    from openlia_server.db.models.auth import User

    user = User(
        id="local",
        email="local@openlia.local",
        display_name="Local",
        is_admin=True,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    from openlia_server.db import session as session_mod

    app = create_app(db_session_factory=session_mod.SessionLocal)
    with TestClient(app) as client:
        yield client


def test_list_empty(personal_client) -> None:
    resp = personal_client.get("/settings/data-providers")
    assert resp.status_code == 200
    assert resp.json() == {"providers": []}


def test_create_provider_returns_201(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "My EODHD",
            "category": "financial",
            "mode": "api_key",
            "api_key": "SECRET",
            "base_url": "https://eodhd.com/api",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "eodhd"
    assert body["label"] == "My EODHD"
    assert "id" in body
    # api_key is never echoed back
    assert "api_key" not in body
    assert body.get("has_api_key") is True


def test_create_with_unknown_kind_returns_400(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "does-not-exist",
            "label": "X",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://x.test",
        },
    )
    assert resp.status_code == 400
    # The error key might be nested under "detail" depending on how Plan 2's error handler works
    body = resp.json()
    # Accept either {"error": "unknown_provider_kind"} or
    # {"detail": {"error": "unknown_provider_kind"}}
    assert body.get("error") == "unknown_provider_kind" or (
        isinstance(body.get("detail"), dict)
        and body["detail"].get("error") == "unknown_provider_kind"
    )


def test_update_label_and_disable(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "A",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.patch(
        f"/settings/data-providers/{pid}",
        json={"label": "A-renamed", "is_enabled": False},
    )
    assert resp2.status_code == 200
    assert resp2.json()["label"] == "A-renamed"
    assert resp2.json()["is_enabled"] is False


def test_delete_provider(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "A",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.delete(f"/settings/data-providers/{pid}")
    assert resp2.status_code == 204
    resp3 = personal_client.get("/settings/data-providers")
    assert resp3.json()["providers"] == []


def test_update_missing_provider_returns_404(personal_client) -> None:
    resp = personal_client.patch(
        "/settings/data-providers/nonexistent-id",
        json={"label": "x"},
    )
    assert resp.status_code == 404


def test_delete_missing_provider_returns_404(personal_client) -> None:
    resp = personal_client.delete("/settings/data-providers/nonexistent-id")
    assert resp.status_code == 404


def test_company_mode_without_session_returns_401(db_session, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "company")
    from openlia_server.db import session as session_mod

    app = create_app(db_session_factory=session_mod.SessionLocal)
    with TestClient(app) as client:
        resp = client.get("/settings/data-providers")
        assert resp.status_code == 401


@respx.mock
def test_test_connection_success(personal_client) -> None:
    respx.get("https://eodhd.com/api/user").mock(
        return_value=httpx.Response(200, json={"email": "x@y.z"})
    )
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.post(f"/settings/data-providers/{pid}/test-connection")
    assert resp2.status_code == 200
    assert resp2.json() == {"ok": True}


@respx.mock
def test_test_connection_failure(personal_client) -> None:
    respx.get("https://eodhd.com/api/user").mock(return_value=httpx.Response(401, text="bad key"))
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.post(f"/settings/data-providers/{pid}/test-connection")
    assert resp2.status_code == 200
    assert resp2.json() == {"ok": False}


def test_auto_map_returns_summary(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    assert resp.status_code == 201
    resp2 = personal_client.post("/settings/data-providers/auto-map")
    assert resp2.status_code == 200, resp2.text
    body = resp2.json()
    assert body["mode"] == "heuristic"
    # EODHD now covers 5 of equity_research's basic+advanced requirements
    # (P0-3-04 added company_fundamentals).
    covered_types = {m["requirement_type"] for m in body["mapped"]}
    assert {
        "stock_quote",
        "historical_prices",
        "company_profile",
        "company_news",
        "company_fundamentals",
    } <= covered_types
    # stock_grade and insider_transactions remain unmet.
    unmet_types = {u["requirement_type"] for u in body["unmet"]}
    assert {"stock_grade", "insider_transactions"} <= unmet_types
    # company_fundamentals must NOT be unmet anymore (P0-3-04 acceptance).
    assert "company_fundamentals" not in unmet_types
    # No duplicate (requirement_type, provider_id) pairs (P0-3-03 acceptance).
    pairs = [(m["requirement_type"], m["provider_id"]) for m in body["mapped"]]
    assert len(pairs) == len({*pairs})


def test_list_requirement_mappings(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    personal_client.post("/settings/data-providers/auto-map")
    resp2 = personal_client.get("/settings/data-providers/mappings")
    assert resp2.status_code == 200
    mappings = resp2.json()["mappings"]
    # At least one mapping for stock_quote pointing at our provider
    assert any(m["requirement_type"] == "stock_quote" and m["provider_id"] == pid for m in mappings)


def test_set_and_delete_individual_mapping(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp_put = personal_client.put(
        "/settings/data-providers/mappings/stock_quote",
        json={"provider_id": pid, "priority": 25},
    )
    assert resp_put.status_code == 200
    assert resp_put.json()["priority"] == 25

    resp_del = personal_client.delete(f"/settings/data-providers/mappings/stock_quote/{pid}")
    assert resp_del.status_code == 204


def test_test_connection_returns_501_for_stub_kind(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "fmp",
            "label": "F",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://fmp.test",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.post(f"/settings/data-providers/{pid}/test-connection")
    assert resp2.status_code == 501
    body = resp2.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "adapter_not_implemented"


def test_create_mcp_provider_roundtrips_via_route(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E-MCP",
            "category": "financial",
            "mode": "mcp",
            "mcp_url": "https://mcp.test/sse",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["mode"] == "mcp"
    assert body["mcp_url"] == "https://mcp.test/sse"

    resp2 = personal_client.get("/settings/data-providers")
    listed = next(p for p in resp2.json()["providers"] if p["id"] == body["id"])
    assert listed["mcp_url"] == "https://mcp.test/sse"
    assert listed["mode"] == "mcp"


def test_create_mcp_provider_without_mcp_url_returns_400(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "bad",
            "category": "financial",
            "mode": "mcp",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "invalid_provider"


def test_patch_provider_priority(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.patch(
        f"/settings/data-providers/{pid}/priority",
        json={"priority": 25},
    )
    assert resp2.status_code == 200
    assert resp2.json() == {"provider_id": pid, "priority": 25}


def test_patch_provider_priority_rejects_negative(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.patch(
        f"/settings/data-providers/{pid}/priority",
        json={"priority": -1},
    )
    assert resp2.status_code == 400


def test_patch_provider_priority_reorders_auto_map(personal_client) -> None:
    a = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "A",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    ).json()["id"]
    b = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "B",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    ).json()["id"]
    personal_client.patch(f"/settings/data-providers/{a}/priority", json={"priority": 50})
    personal_client.patch(f"/settings/data-providers/{b}/priority", json={"priority": 10})

    resp = personal_client.post("/settings/data-providers/auto-map")
    body = resp.json()
    # B (priority 10) wins; only B is mapped.
    for entry in body["mapped"]:
        assert entry["provider_id"] == b
