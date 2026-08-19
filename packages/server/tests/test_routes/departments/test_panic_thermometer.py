"""HTTP tests for /departments/panic_thermometer/*."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from openlia_server.services.pt_runner import PtRunner


@dataclass
class _PtTestDispatcher:
    payloads: dict[tuple[str, str], Any]

    def fetch(
        self,
        *,
        requirement: str,
        panel_id: str,
        params: dict[str, Any],
    ) -> Any:
        return self.payloads.get((panel_id, requirement))


def _default_test_dispatcher() -> _PtTestDispatcher:
    history = [
        {
            "date": f"2026-03-{i:02d}",
            "open": 90.0,
            "high": 95.0,
            "low": 88.0,
            "close": 90.0 + i * 0.1,
            "volume": 0,
        }
        for i in range(1, 99)
    ]
    quote = {"price": 98.5, "previous_close": 97.9}
    return _PtTestDispatcher(
        payloads={
            ("oil", "historical_prices"): history,
            ("oil", "stock_quote"): quote,
            ("inflation", "historical_prices"): [],
            ("inflation", "stock_quote"): None,
            ("inflation", "economic_events"): [],
            ("fed_language", "company_news"): [],
            ("fed_language", "economic_events"): [],
            ("wage_growth", "economic_events"): [],
            ("diplomacy", "company_news"): [],
        }
    )


@pytest.fixture
def pt_client(company_client, auth_user):
    """Install a deterministic PT dispatcher on the shared singleton runner."""
    from openlia_server.db import session as session_mod

    disp = _default_test_dispatcher()
    company_client.app.state.pt_dispatcher = disp
    company_client.app.state.pt_runner = PtRunner(
        session_factory=session_mod.SessionLocal, dispatcher=disp
    )
    return company_client


# --- Dashboard route ---------------------------------------------------------


def test_dashboard_returns_json(pt_client):
    r = pt_client.get("/departments/panic_thermometer/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert set(body["panels"].keys()) == {
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    }
    assert "composite" in body and "level" in body["composite"]
    assert "generated_at" in body


def test_dashboard_requires_auth(company_client):
    r = company_client.get("/departments/panic_thermometer/dashboard")
    assert r.status_code == 401


# --- Config GET / PUT --------------------------------------------------------


def test_get_config_returns_default_on_first_visit(pt_client):
    r = pt_client.get("/departments/panic_thermometer/config")
    assert r.status_code == 200
    body = r.json()
    assert {p["panel_id"] for p in body["panel_config"]} == {
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    }
    assert body["composite_settings"]["mode"] == "count"


def test_put_config_persists_changes(pt_client):
    current = pt_client.get("/departments/panic_thermometer/config").json()
    current["composite_settings"]["red_threshold"] = 4
    r = pt_client.put("/departments/panic_thermometer/config", json=current)
    assert r.status_code == 200
    reread = pt_client.get("/departments/panic_thermometer/config").json()
    assert reread["composite_settings"]["red_threshold"] == 4


# --- Presets ----------------------------------------------------------------


def test_list_presets_includes_shipped(pt_client):
    r = pt_client.get("/departments/panic_thermometer/presets")
    assert r.status_code == 200
    body = r.json()
    shipped = [p for p in body if p["is_shipped"]]
    assert len(shipped) >= 15


def test_create_and_delete_user_preset(pt_client):
    r = pt_client.post(
        "/departments/panic_thermometer/presets",
        json={"name": "my-custom", "description": "notes"},
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    listing = pt_client.get("/departments/panic_thermometer/presets").json()
    assert any(p["id"] == pid for p in listing)
    d = pt_client.delete(f"/departments/panic_thermometer/presets/{pid}")
    assert d.status_code == 204


def test_update_user_preset(pt_client):
    p = pt_client.post(
        "/departments/panic_thermometer/presets",
        json={"name": "n1", "description": None},
    ).json()
    r = pt_client.put(
        f"/departments/panic_thermometer/presets/{p['id']}",
        json={"name": "renamed", "description": "updated"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"


def test_apply_shipped_oil_ma_relative(pt_client):
    listing = pt_client.get("/departments/panic_thermometer/presets").json()
    oil_ma = next(p for p in listing if p["name"] == "oil::ma_relative" and p["is_shipped"])
    r = pt_client.post(f"/departments/panic_thermometer/presets/{oil_ma['id']}/apply")
    assert r.status_code == 200
    oil_panel = next(p for p in r.json()["panel_config"] if p["panel_id"] == "oil")
    assert oil_panel["streak_condition"] == "price > ma200 * ma_multiplier"


# --- Import / Export --------------------------------------------------------


def test_export_returns_version_1_payload(pt_client):
    r = pt_client.get("/departments/panic_thermometer/config/export")
    body = r.json()
    assert body["version"] == 1
    assert len(body["panel_config"]) == 5


def test_import_round_trip(pt_client):
    export = pt_client.get("/departments/panic_thermometer/config/export").json()
    export["composite_settings"]["red_threshold"] = 5
    r = pt_client.post("/departments/panic_thermometer/config/import", json=export)
    assert r.status_code == 200
    reread = pt_client.get("/departments/panic_thermometer/config/export").json()
    assert reread["composite_settings"]["red_threshold"] == 5


def test_import_rejects_v2(pt_client):
    r = pt_client.post(
        "/departments/panic_thermometer/config/import",
        json={"version": 2, "panel_config": [], "composite_settings": {}},
    )
    assert r.status_code == 400
    assert "unsupported" in r.json()["detail"].lower()


# --- Formula parse / test / preview -----------------------------------------


def test_formula_parse_valid(pt_client):
    r = pt_client.post(
        "/departments/panic_thermometer/formula/parse",
        json={"formula": "price > 85", "panel": "oil"},
    )
    body = r.json()
    assert body["ok"] is True
    assert "price" in body["identifiers"]


def test_formula_parse_syntax_error(pt_client):
    r = pt_client.post(
        "/departments/panic_thermometer/formula/parse",
        json={"formula": "price >>>", "panel": "oil"},
    )
    body = r.json()
    assert body["ok"] is False
    assert body["errors"][0]["type"] == "parse"


def test_formula_test_with_cached_data(pt_client):
    pt_client.get("/departments/panic_thermometer/dashboard")  # warm cache
    r = pt_client.post(
        "/departments/panic_thermometer/formula/test",
        json={"formula": "price > 0", "panel": "oil", "params": {}},
    )
    body = r.json()
    assert body["value"] is True


def test_ruleset_preview_with_cached_data(pt_client):
    pt_client.get("/departments/panic_thermometer/dashboard")
    r = pt_client.post(
        "/departments/panic_thermometer/ruleset/preview",
        json={
            "panel": "oil",
            "ruleset": {
                "rules": [
                    {"status": "red", "formula": "price > 0", "label": "hit"},
                    {"status": "green", "formula": "true", "label": "miss"},
                ],
                "params": {},
                "streak_condition": None,
            },
        },
    )
    body = r.json()
    assert body["status"] == "red"
    assert body["label"] == "hit"


# --- App wiring -------------------------------------------------------------


def test_pt_router_mounted(company_client):
    r = company_client.get("/openapi.json")
    paths = r.json()["paths"]
    assert "/departments/panic_thermometer/dashboard" in paths
    assert "/departments/panic_thermometer/config" in paths
    assert "/departments/panic_thermometer/presets" in paths
    assert "/departments/panic_thermometer/formula/parse" in paths


def test_seed_runs_on_startup(company_client, db_session):
    from openlia_server.db.models.dashboard import PtPreset

    # Route a request so app factory + lifespan has definitely run.
    company_client.get("/healthz")
    rows = db_session.query(PtPreset).filter_by(is_shipped=True).all()
    assert len(rows) == 15


# --- NEW-18-12 — additional coverage --------------------------------------


def test_dashboard_emits_warnings_for_missing_payloads(pt_client):
    # Default test dispatcher provides only oil data; other panels emit warnings.
    body = pt_client.get("/departments/panic_thermometer/dashboard").json()
    assert any(panel.get("warnings") for panel in body["panels"].values())


def test_dashboard_records_trigger_event_on_first_run(pt_client, db_session):
    from openlia_server.db.models.dashboard import PtTriggerEvent

    pt_client.get("/departments/panic_thermometer/dashboard")
    rows = db_session.query(PtTriggerEvent).all()
    assert len(rows) >= 1


def test_formula_test_returns_resolved_values(pt_client):
    pt_client.get("/departments/panic_thermometer/dashboard")
    r = pt_client.post(
        "/departments/panic_thermometer/formula/test",
        json={"formula": "price > price_threshold", "panel": "oil", "params": {}},
    )
    body = r.json()
    assert "price" in body["resolved_values"]
    assert "price_threshold" in body["resolved_values"]


def test_formula_test_without_warmed_cache_returns_409(pt_client):
    r = pt_client.post(
        "/departments/panic_thermometer/formula/test",
        json={"formula": "price > 0", "panel": "oil", "params": {}},
    )
    assert r.status_code == 409


def test_apply_preset_then_dashboard_reflects_streak_condition(pt_client):
    listing = pt_client.get("/departments/panic_thermometer/presets").json()
    oil_ma = next(p for p in listing if p["name"] == "oil::ma_relative" and p["is_shipped"])
    pt_client.post(f"/departments/panic_thermometer/presets/{oil_ma['id']}/apply")
    body = pt_client.get("/departments/panic_thermometer/config").json()
    oil = next(p for p in body["panel_config"] if p["panel_id"] == "oil")
    assert oil["streak_condition"] == "price > ma200 * ma_multiplier"


# --- Dashboard snapshot cache (audit follow-up F2) ---------------------------


def test_dashboard_serves_cached_payload_without_recompute(pt_client):
    """A fresh pt_dashboard_cache row is served as-is — no runner compute."""
    first = pt_client.get("/departments/panic_thermometer/dashboard")
    assert first.status_code == 200

    calls = {"n": 0}
    real = pt_client.app.state.pt_runner.compute_dashboard

    def _counting(user_id):
        calls["n"] += 1
        return real(user_id)

    pt_client.app.state.pt_runner.compute_dashboard = _counting
    try:
        second = pt_client.get("/departments/panic_thermometer/dashboard")
    finally:
        pt_client.app.state.pt_runner.compute_dashboard = real

    assert second.status_code == 200
    assert calls["n"] == 0
    assert second.json() == first.json()


def test_config_update_invalidates_dashboard_cache(pt_client):
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.dashboard import PtDashboardCache

    assert pt_client.get("/departments/panic_thermometer/dashboard").status_code == 200
    with session_mod.SessionLocal() as s:
        assert s.query(PtDashboardCache).count() == 1

    cfg = pt_client.get("/departments/panic_thermometer/config").json()
    r = pt_client.put(
        "/departments/panic_thermometer/config",
        json={
            "panel_config": cfg["panel_config"],
            "composite_settings": cfg["composite_settings"],
        },
    )
    assert r.status_code == 200

    with session_mod.SessionLocal() as s:
        assert s.query(PtDashboardCache).count() == 0
