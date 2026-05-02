"""Tests for the dept-health cache + invalidation hooks (Phase 10 Task 10.2)."""

from __future__ import annotations

import uuid

import pytest
from openlia.connectors.types import Category
from openlia_server.db.models.connectors import Connector
from openlia_server.services import connectors_service, dept_health


def _make_connector_row(
    *,
    category: str = "financial",
    status: str = "validated",
) -> Connector:
    return Connector(
        id=str(uuid.uuid4()),
        provider_id="prov_" + uuid.uuid4().hex[:6],
        display_name="P",
        source="cli_mcp",
        category=category,
        launch={"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
        secrets={},
        cached_tools=[{"name": "t", "description": "", "input_schema": {}}],
        status=status,
    )


def test_compute_all_returns_entry_for_every_registered_dept(db_session):
    health = dept_health.compute_all(db_session)
    expected = {
        "secretary",
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "panic_thermometer",
        "macro_research",
        "retail_sentiment",
    }
    assert set(health.keys()) == expected


def test_compute_all_active_when_required_validated_connector_present(db_session):
    db_session.add(_make_connector_row(category="financial", status="validated"))
    db_session.commit()
    health = dept_health.compute_all(db_session)
    # Equity Research requires financial only; should be active.
    assert health["equity_research"].status == "active"


def test_compute_all_disabled_when_no_validated_connectors(db_session):
    health = dept_health.compute_all(db_session)
    # Equity Research requires financial — without any connector it must be disabled.
    er = health["equity_research"]
    assert er.status == "disabled"
    assert Category.FINANCIAL in er.missing_categories


def test_serialize_shape():
    from openlia.departments.health import DepartmentHealth

    h = DepartmentHealth(
        department_id="x",
        status="disabled",
        reason="Missing required categories: financial",
        missing_categories=[Category.FINANCIAL],
        unresolved_needs=["q"],
    )
    blob = dept_health.serialize(h)
    # Unknown dept id → registry-derived fields are empty lists.
    assert blob == {
        "department_id": "x",
        "status": "disabled",
        "reason": "Missing required categories: financial",
        "missing_categories": ["financial"],
        "unresolved_needs": ["q"],
        "required_categories": [],
        "required_any_of": [],
        "unsatisfied_any_of": [],
    }


def test_serialize_includes_registry_metadata_for_known_dept():
    """For a real dept, serialize echoes the static registry metadata so
    the wizard can show 'required vs. alternative' category badges."""
    from openlia.departments.health import DepartmentHealth

    h = DepartmentHealth(
        department_id="morning_briefing",
        status="disabled",
        reason="...",
        missing_categories=[],
        unresolved_needs=[],
        unsatisfied_any_of=[(Category.NEWS, Category.WEB_SEARCH)],
    )
    blob = dept_health.serialize(h)
    assert blob["required_categories"] == ["financial"]
    assert blob["required_any_of"] == [["news", "web_search"]]
    assert blob["unsatisfied_any_of"] == [["news", "web_search"]]


def test_serialize_macro_research_shows_web_search_required():
    from openlia.departments.health import DepartmentHealth

    h = DepartmentHealth(
        department_id="macro_research",
        status="active",
        reason=None,
        missing_categories=[],
        unresolved_needs=[],
    )
    blob = dept_health.serialize(h)
    assert "financial" in blob["required_categories"]
    assert "web_search" in blob["required_categories"]


@pytest.mark.asyncio
async def test_connector_create_triggers_invalidation(db_session_factory, monkeypatch):
    """Creating a validated connector must refresh the health cache."""
    captured: dict = {"calls": 0, "last": None}

    def hook(session):
        captured["calls"] += 1
        captured["last"] = dept_health.compute_all(session)

    connectors_service.set_dept_health_hook(hook)
    try:

        async def fake(launch, secrets):
            return connectors_service.ValidationOk(
                tools=[{"name": "t", "description": "", "input_schema": {}}],
                python_callables=[],
            )

        monkeypatch.setattr(connectors_service, "_validate_launch", fake)

        with db_session_factory() as session:
            await connectors_service.create_connector(
                session,
                provider_id="eodhd",
                display_name="EODHD",
                source=__import__(
                    "openlia.connectors.types", fromlist=["ConnectorSource"]
                ).ConnectorSource.CLI_MCP,
                category=Category.FINANCIAL,
                launch={"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
                secrets={},
            )

        assert captured["calls"] == 1
        # Equity Research now active.
        assert captured["last"]["equity_research"].status == "active"
    finally:
        connectors_service.set_dept_health_hook(None)


@pytest.mark.asyncio
async def test_connector_delete_triggers_invalidation(db_session_factory):
    """Deleting a connector must re-run the health cache hook."""
    seen: list[str] = []

    def hook(session):
        seen.append("called")

    # Seed a validated connector directly.
    with db_session_factory() as session:
        row = _make_connector_row()
        session.add(row)
        session.commit()
        cid = row.id

    connectors_service.set_dept_health_hook(hook)
    try:
        with db_session_factory() as session:
            connectors_service.delete_connector(session, cid)
        assert seen == ["called"]
    finally:
        connectors_service.set_dept_health_hook(None)


def test_app_state_dept_health_populated_at_factory_time(db_session_factory):
    """create_app() should install the recompute hooks and a cache map."""
    from openlia_server.app import create_app

    app = create_app(db_session_factory=db_session_factory)
    # The factory installs an empty dict; the lifespan populates on startup.
    assert isinstance(app.state.dept_health, dict)
    # Hooks are installed (set to a non-None callable).
    assert connectors_service._invalidation_hook is not None
