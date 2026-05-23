"""Route integration tests for v2.3 equity-research suspend/resume endpoints.

PR3 scope: prove the CLARIFY suspend/resume control flow works end-to-end
through the FastAPI surface. The runner factory is stubbed with a
FakeClarifierClient + NoOp stages so we are testing the route layer +
service layer + persistence, not real LLM behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.report_v2_3.clients.clarifier import FakeClarifierClient
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyNeedsInput,
    ClarifyProceed,
    ClarifyQuestion,
)
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.services.v2_3_runner_factory import make_v2_3_runner_factory


@pytest.fixture
def v2_3_client(tmp_path, monkeypatch):
    """TestClient + a temp SQLite + an authenticated local user."""
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/v23.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/v23.db")
    Base.metadata.create_all(session_mod.get_engine())

    with session_mod.SessionLocal() as s:
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

    app = create_app(db_session_factory=session_mod.SessionLocal)
    try:
        yield app, TestClient(app)
    finally:
        session_mod.dispose_engine()


def _start_payload() -> dict:
    return {
        "raw_prompt": "write an initiation on NVDA",
        "language": "en",
        "report_type": "initiation",
        "tickers": ["NVDA"],
    }


def _install_factory(app, client: FakeClarifierClient) -> None:
    app.state.v2_3_runner_factory = make_v2_3_runner_factory(client)


# ---------------------------------------------------------------------------
# Engine availability
# ---------------------------------------------------------------------------


def test_start_returns_503_when_factory_not_wired(v2_3_client) -> None:
    _, client = v2_3_client
    resp = client.post("/api/departments/equity-research/v2.3/runs", json=_start_payload())
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "v2_3_engine_unavailable"


# ---------------------------------------------------------------------------
# Proceed path — single call completes the run
# ---------------------------------------------------------------------------


def test_proceed_path_runs_to_completion(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app,
        FakeClarifierClient(result=ClarifyProceed(assumptions=["audience: PM"])),
    )

    resp = client.post("/api/departments/equity-research/v2.3/runs", json=_start_payload())
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "complete"
    assert body["clarify_result"] == {
        "outcome": "proceed",
        "assumptions": ["audience: PM"],
        "questions": [],
    }
    assert body["pending_questions"] == []


# ---------------------------------------------------------------------------
# Suspend -> answer -> complete
# ---------------------------------------------------------------------------


def test_suspend_then_answer_completes_run(v2_3_client) -> None:
    app, client = v2_3_client

    question = ClarifyQuestion(
        id="horizon",
        question="what horizon?",
        why_blocking="drives the model",
        default="12 months",
    )

    # Suspend on the first call, proceed on the resumed call. The stage handles
    # resume internally — it bypasses the client — so only the first invocation
    # needs to hit the fake.
    fake = FakeClarifierClient(result=ClarifyNeedsInput(questions=[question]))
    _install_factory(app, fake)

    start = client.post("/api/departments/equity-research/v2.3/runs", json=_start_payload())
    assert start.status_code == 200, start.text
    started = start.json()
    assert started["status"] == "waiting_on_user"
    assert started["current_stage"] == "clarify"
    assert len(started["pending_questions"]) == 1
    assert started["pending_questions"][0]["id"] == "horizon"

    run_id = started["run_id"]

    answer = client.post(
        f"/api/departments/equity-research/v2.3/runs/{run_id}/answer",
        json={"answers": {"horizon": "24 months"}},
    )
    assert answer.status_code == 200, answer.text
    answered = answer.json()
    assert answered["status"] == "complete"
    assert answered["pending_questions"] == []
    assert answered["clarify_result"]["outcome"] == "proceed"
    assert answered["clarify_result"]["assumptions"] == ["horizon: 24 months"]
    # The fake client was hit exactly once — resume must NOT re-invoke it.
    assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# GET status endpoint
# ---------------------------------------------------------------------------


def test_get_run_returns_persisted_state(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app, FakeClarifierClient(result=ClarifyProceed(assumptions=["x"]))
    )

    start = client.post("/api/departments/equity-research/v2.3/runs", json=_start_payload())
    run_id = start.json()["run_id"]

    got = client.get(f"/api/departments/equity-research/v2.3/runs/{run_id}")
    assert got.status_code == 200
    body = got.json()
    assert body["run_id"] == run_id
    assert body["status"] == "complete"


def test_get_run_returns_404_for_unknown_run_id(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed()))

    resp = client.get("/api/departments/equity-research/v2.3/runs/ghost")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "run_not_found"


def test_answer_returns_404_for_unknown_run_id(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed()))

    resp = client.post(
        "/api/departments/equity-research/v2.3/runs/ghost/answer",
        json={"answers": {}},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "run_not_found"


def test_answer_returns_409_when_run_is_not_waiting(v2_3_client) -> None:
    """A completed run cannot be `answer`ed — resume() requires WAITING_ON_USER."""
    app, client = v2_3_client
    _install_factory(
        app, FakeClarifierClient(result=ClarifyProceed(assumptions=["x"]))
    )

    start = client.post("/api/departments/equity-research/v2.3/runs", json=_start_payload())
    run_id = start.json()["run_id"]

    resp = client.post(
        f"/api/departments/equity-research/v2.3/runs/{run_id}/answer",
        json={"answers": {}},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "invalid_run_state"
