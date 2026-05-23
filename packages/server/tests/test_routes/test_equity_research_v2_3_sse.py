"""SSE route tests for the v2.3 pipeline.

Streams stage events from a stubbed runner factory + FakeClarifierClient.
Real LLM behavior is out of scope here — we verify the SSE framing,
event ordering, and the trailing ``state`` frame.
"""

from __future__ import annotations

import json
import re
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
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/v23sse.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/v23sse.db")
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
        "raw_prompt": "initiate on NVDA",
        "language": "en",
        "report_type": "initiation",
        "tickers": ["NVDA"],
    }


def _install_factory(app, client: FakeClarifierClient) -> None:
    app.state.v2_3_runner_factory = make_v2_3_runner_factory(client)


def _parse_sse(body: str) -> list[dict]:
    """Split a text/event-stream body into ``[{event, data}]`` records."""
    out: list[dict] = []
    for chunk in re.split(r"\n\n", body.strip()):
        evt = None
        data = None
        for line in chunk.splitlines():
            if line.startswith("event: "):
                evt = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        if evt is not None and data is not None:
            out.append({"event": evt, "data": json.loads(data)})
    return out


# ---------------------------------------------------------------------------
# Engine availability
# ---------------------------------------------------------------------------


def test_stream_returns_503_when_factory_not_wired(v2_3_client) -> None:
    _, client = v2_3_client
    resp = client.post(
        "/api/departments/equity-research/v2.3/runs/stream",
        json=_start_payload(),
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "v2_3_engine_unavailable"


# ---------------------------------------------------------------------------
# Proceed path — stream emits stage events + completed + state
# ---------------------------------------------------------------------------


def test_proceed_path_streams_completed(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app,
        FakeClarifierClient(result=ClarifyProceed(assumptions=["audience: PM"])),
    )

    with client.stream(
        "POST",
        "/api/departments/equity-research/v2.3/runs/stream",
        json=_start_payload(),
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse(body)
    kinds = [e["event"] for e in events]

    # Sanity: a stage_started/stage_completed pair for every pipeline slot
    # the all-NoOp runner walks (8 slots), plus completed + state.
    assert kinds.count("stage_started") == 8
    assert kinds.count("stage_completed") == 8
    assert "completed" in kinds
    # The very last event is `state` and carries the final RunStateOut.
    assert events[-1]["event"] == "state"
    state = events[-1]["data"]
    assert state["status"] == "complete"
    assert state["clarify_result"]["outcome"] == "proceed"


# ---------------------------------------------------------------------------
# Suspend path — stream emits suspended + state
# ---------------------------------------------------------------------------


def test_suspend_path_streams_suspended(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app,
        FakeClarifierClient(
            result=ClarifyNeedsInput(
                questions=[
                    ClarifyQuestion(
                        id="horizon",
                        question="What horizon?",
                        why_blocking="drives DCF",
                        default="12 months",
                    ),
                ]
            )
        ),
    )

    with client.stream(
        "POST",
        "/api/departments/equity-research/v2.3/runs/stream",
        json=_start_payload(),
    ) as resp:
        assert resp.status_code == 200
        body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse(body)
    kinds = [e["event"] for e in events]

    # CLARIFY started + suspended; no later stages.
    assert kinds[:2] == ["stage_started", "suspended"]
    suspended = events[1]["data"]
    assert suspended["slot"] == "clarify"
    assert len(suspended["questions"]) == 1
    assert suspended["questions"][0]["id"] == "horizon"

    # Final state frame carries the persisted suspended state.
    assert events[-1]["event"] == "state"
    state = events[-1]["data"]
    assert state["status"] == "waiting_on_user"
    assert state["current_stage"] == "clarify"
    assert len(state["pending_questions"]) == 1


# ---------------------------------------------------------------------------
# Resume via /answer/stream
# ---------------------------------------------------------------------------


def test_answer_stream_resumes_to_completion(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app,
        FakeClarifierClient(
            result=ClarifyNeedsInput(
                questions=[
                    ClarifyQuestion(
                        id="horizon",
                        question="What horizon?",
                        why_blocking="drives DCF",
                        default="12 months",
                    ),
                ]
            )
        ),
    )

    # Start a run that suspends.
    with client.stream(
        "POST",
        "/api/departments/equity-research/v2.3/runs/stream",
        json=_start_payload(),
    ) as resp:
        body = "".join(chunk for chunk in resp.iter_text())
    events = _parse_sse(body)
    run_id = events[-1]["data"]["run_id"]

    # Resume.
    with client.stream(
        "POST",
        f"/api/departments/equity-research/v2.3/runs/{run_id}/answer/stream",
        json={"answers": {"horizon": "5 years"}},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse(body)
    kinds = [e["event"] for e in events]
    assert "completed" in kinds
    final = events[-1]
    assert final["event"] == "state"
    assert final["data"]["status"] == "complete"


# ---------------------------------------------------------------------------
# Error surface during streaming
# ---------------------------------------------------------------------------


def test_answer_stream_emits_failed_frame_for_unknown_run(v2_3_client) -> None:
    app, client = v2_3_client
    _install_factory(
        app,
        FakeClarifierClient(result=ClarifyProceed()),
    )

    with client.stream(
        "POST",
        "/api/departments/equity-research/v2.3/runs/does-not-exist/answer/stream",
        json={"answers": {}},
    ) as resp:
        body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse(body)
    assert events
    last = events[-1]
    assert last["event"] == "failed"
    assert last["data"]["status"] == 404
