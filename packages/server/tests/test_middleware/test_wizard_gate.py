"""Tests for wizard_gate dependency — 410 Gone after completion."""
from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.middleware.wizard_gate import require_wizard_active


@pytest.fixture
def app_with_gate(db_session_factory):
    app = FastAPI()

    from openlia_server.db.session import get_db_session

    @app.get("/setup/mode")
    def setup_mode(db=Depends(get_db_session), _=Depends(require_wizard_active)):
        return {"ok": True}

    return TestClient(app)


def test_wizard_active_allows_request(app_with_gate) -> None:
    resp = app_with_gate.get("/setup/mode")
    assert resp.status_code == 200


def test_wizard_completed_returns_410(app_with_gate, db_session) -> None:
    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.commit()

    resp = app_with_gate.get("/setup/mode")
    assert resp.status_code == 410
    assert resp.json()["detail"]["code"] == "wizard_completed"
