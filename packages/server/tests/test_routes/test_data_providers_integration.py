"""End-to-end integration: configure provider → auto-map → query capability."""

from datetime import UTC, datetime

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from openlia.data.adapters import ADAPTERS
from openlia.data.resolver import resolve_provider_for_capability
from openlia_server.app import create_app
from openlia_server.db.models.auth import User
from openlia_server.services import data_providers as svc


@pytest.fixture
def personal_client(db_session, monkeypatch):
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
    app = create_app(db_session_factory=lambda: db_session)
    with TestClient(app) as c:
        yield c


@respx.mock
def test_full_flow_provider_then_resolver_then_adapter(
    personal_client,
    db_session,
) -> None:
    # 1. Admin creates provider
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "EODHD",
            "category": "financial",
            "mode": "api_key",
            "api_key": "test-key",
            "base_url": "https://eodhd.com/api",
        },
    )
    assert resp.status_code == 201
    pid = resp.json()["id"]

    # 2. Admin triggers auto-map
    resp2 = personal_client.post("/settings/data-providers/auto-map")
    assert resp2.status_code == 200

    # 3. Resolver (as Plan 5 will use it) finds the provider for stock_quote
    entries = svc.load_entries_for_capability(db_session, capability="stock_quote")
    assert len(entries) == 1
    assert entries[0].id == pid

    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=ADAPTERS,
    )
    assert resolved is not None
    assert resolved.entry.kind == "eodhd"

    # 4. Adapter (constructed from the entry) can fetch
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(200, json={"code": "AAPL.US", "close": 225.1}),
    )
    # We don't run the async coroutine here — just confirm the adapter class
    # can be instantiated from the loaded entry.
    adapter = resolved.adapter_cls(resolved.entry)
    assert adapter.kind == "eodhd"
    assert adapter.entry.api_key == "test-key"
