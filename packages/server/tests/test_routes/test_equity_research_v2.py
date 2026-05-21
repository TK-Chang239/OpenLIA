"""Tests for the v2.2 SSE endpoints (Steps 3 + 4).

The route layer is verified with a stub stage factory that returns a fake
``RunnerV2`` yielding canned events. Real LLM integration is out of scope
for the route tests — what matters here is event → SSE frame translation
and persistence transitions (mark_paused on pause, mark_completed on
completion, mark_failed on error).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.report_v2.runner_v2 import (
    ClarifierPaused,
    Completed,
    Failed,
    PipelineStage,
    StageCompleted,
    StageStarted,
)
from openlia.llm.runtime.report_v2.schemas.clarifier import (
    CapabilityWarning,
    ClarifierOutput,
)
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary
from openlia.llm.runtime.report_v2.schemas.verification_history import (
    VerificationHistory,
)
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.services import pipeline_run_service as svc


class _FakeRunner:
    """Stand-in for RunnerV2 — yields a scripted event list on execute()."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.called_with: dict[str, Any] = {}

    def execute(
        self, composer_inputs: dict[str, Any], template_spec: Any, *, resume_state=None
    ):
        self.called_with = {
            "composer_inputs": composer_inputs,
            "template_spec": template_spec,
            "resume_state": resume_state,
        }
        yield from self._events


@pytest.fixture
def v2_client(tmp_path, monkeypatch):
    """Spin up a TestClient with a temp SQLite + an authenticated local user."""
    import openlia_server.db.models.register_all  # noqa: F401 — register all ORM models

    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/v2.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/v2.db")
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


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    frames: list[tuple[str, dict]] = []
    event: str | None = None
    for line in body.splitlines():
        if line.startswith("event: "):
            event = line[len("event: ") :]
        elif line.startswith("data: ") and event is not None:
            frames.append((event, json.loads(line[len("data: ") :])))
            event = None
    return frames


def _ok_payload() -> dict:
    return {
        "user_input": "Generate AAPL report",
        "report_template_id": "stock_research_v2",
        "composer_inputs": {"ticker": "AAPL"},
    }


# ---------------------------------------------------------------------------
# Start endpoint — happy path
# ---------------------------------------------------------------------------


def test_start_emits_stage_frames_and_completed_frame(v2_client):
    app, client = v2_client
    fake_run_summary = RunSummary(
        engine_version="2.2",
        template_id="stock_research_v2",
        template_name="Stock Research (v2)",
        composer_inputs={"ticker": "AAPL"},
        outcomes=[],
    )
    runner = _FakeRunner(
        events=[
            StageStarted(PipelineStage.CLARIFY),
            StageCompleted(PipelineStage.CLARIFY),
            StageStarted(PipelineStage.RESEARCH_PLAN),
            StageCompleted(PipelineStage.RESEARCH_PLAN),
            Completed(
                html="<article>OK</article>",
                run_summary=fake_run_summary,
                verification_history=VerificationHistory(),
            ),
        ]
    )
    app.state.v2_runner_stage_factory = lambda ctx: runner

    resp = client.post(
        "/api/departments/equity-research/v2/report", json=_ok_payload()
    )
    assert resp.status_code == 200

    frames = _parse_sse(resp.text)
    events = [e for e, _ in frames]
    assert events == [
        "stage.started",
        "stage.completed",
        "stage.started",
        "stage.completed",
        "completed",
    ]
    run_id = resp.headers["X-Run-Id"]
    assert frames[-1][1]["run_id"] == run_id
    assert frames[-1][1]["html"] == "<article>OK</article>"

    # Persistence: row landed in COMPLETED state.
    with session_mod.SessionLocal() as s:
        row = svc.get_run(s, run_id)
        assert row is not None
        assert row.state == "COMPLETED"
        assert row.completed_at is not None


# ---------------------------------------------------------------------------
# Start endpoint — clarifier pause
# ---------------------------------------------------------------------------


def test_start_pauses_and_persists_on_clarifier_warnings(v2_client):
    app, client = v2_client
    output = ClarifierOutput(
        questions=[],
        blocking_warnings=[
            CapabilityWarning(
                capability_id="extra_passes",
                detected_phrase="devil's advocate",
                user_message="not supported",
                available_actions=["proceed_without", "cancel_and_edit", "clarify"],
            )
        ],
        notices=[],
        detected_intents=["extra_passes"],
    )
    runner = _FakeRunner(
        events=[
            StageStarted(PipelineStage.CLARIFY),
            StageCompleted(PipelineStage.CLARIFY),
            ClarifierPaused(
                output=output,
                round=1,
                clarification_history=[output],
            ),
        ]
    )
    app.state.v2_runner_stage_factory = lambda ctx: runner

    resp = client.post(
        "/api/departments/equity-research/v2/report", json=_ok_payload()
    )
    assert resp.status_code == 200

    frames = _parse_sse(resp.text)
    pause_frames = [d for e, d in frames if e == "clarifier.pause"]
    assert len(pause_frames) == 1
    assert pause_frames[0]["round"] == 1
    assert (
        pause_frames[0]["output"]["blocking_warnings"][0]["capability_id"]
        == "extra_passes"
    )

    run_id = resp.headers["X-Run-Id"]
    with session_mod.SessionLocal() as s:
        row = svc.get_run(s, run_id)
        assert row is not None
        assert row.state == "CLARIFY_AWAITING_USER"
        assert row.paused_at is not None
        assert row.last_clarifier_round == 1


# ---------------------------------------------------------------------------
# Start endpoint — failed
# ---------------------------------------------------------------------------


def test_start_marks_failed_when_runner_yields_failed(v2_client):
    app, client = v2_client
    runner = _FakeRunner(
        events=[Failed(stage=PipelineStage.RESEARCH_PLAN, reason="planner blew up")]
    )
    app.state.v2_runner_stage_factory = lambda ctx: runner

    resp = client.post(
        "/api/departments/equity-research/v2/report", json=_ok_payload()
    )
    assert resp.status_code == 200

    frames = _parse_sse(resp.text)
    failed = [d for e, d in frames if e == "failed"]
    assert len(failed) == 1
    assert failed[0]["stage"] == "research_plan"
    assert "planner blew up" in failed[0]["reason"]

    run_id = resp.headers["X-Run-Id"]
    with session_mod.SessionLocal() as s:
        row = svc.get_run(s, run_id)
        assert row is not None
        assert row.state == "FAILED"
        assert "planner blew up" in (row.failure_reason or "")


# ---------------------------------------------------------------------------
# Factory missing
# ---------------------------------------------------------------------------


def test_start_returns_503_when_factory_unset(v2_client):
    app, client = v2_client
    # Do not set app.state.v2_runner_stage_factory.
    resp = client.post(
        "/api/departments/equity-research/v2/report", json=_ok_payload()
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "v2_engine_unavailable"


# ---------------------------------------------------------------------------
# Resume endpoint
# ---------------------------------------------------------------------------


def test_resume_re_streams_pipeline_with_user_answers(v2_client):
    app, client = v2_client

    # Seed a paused run row directly.
    with session_mod.SessionLocal() as s:
        run = svc.create_run(
            s,
            user_id="local",
            session_id=None,
            department="equity_research",
            template_id="stock_research_v2",
            template_raw=_bundled_template_raw("stock_research_v2"),
            template_format="yaml",
            composer_inputs={"ticker": "AAPL", "prompt": "x"},
        )
        svc.mark_paused(
            s,
            run.id,
            stage="clarify",
            clarifier_output={
                "questions": [],
                "blocking_warnings": [],
                "notices": [],
                "detected_intents": [],
            },
            clarifier_round=1,
            clarification_history=[],
        )
        s.commit()
        run_id = run.id

    fake_run_summary = RunSummary(
        engine_version="2.2",
        template_id="stock_research_v2",
        template_name="Stock Research (v2)",
        composer_inputs={},
        outcomes=[],
    )
    runner = _FakeRunner(
        events=[
            StageStarted(PipelineStage.RESEARCH_PLAN),
            StageCompleted(PipelineStage.RESEARCH_PLAN),
            Completed(
                html="<article>done</article>",
                run_summary=fake_run_summary,
                verification_history=VerificationHistory(),
            ),
        ]
    )
    app.state.v2_runner_stage_factory = lambda ctx: runner

    resp = client.post(
        f"/api/departments/equity-research/v2/runs/{run_id}/resume",
        json={
            "warning_actions": {"extra_passes": "proceed_without"},
            "clarifications": {},
            "question_answers": {},
        },
    )
    assert resp.status_code == 200

    frames = _parse_sse(resp.text)
    assert ("completed", {"run_id": run_id, "html": "<article>done</article>"}) in frames

    # Resume passed the answers payload into the runner.
    assert runner.called_with["resume_state"] is not None
    assert (
        runner.called_with["resume_state"].answers["warning_actions"][
            "extra_passes"
        ]
        == "proceed_without"
    )

    # Run row now COMPLETED.
    with session_mod.SessionLocal() as s:
        row = svc.get_run(s, run_id)
        assert row is not None
        assert row.state == "COMPLETED"


def test_resume_rejects_run_in_wrong_state(v2_client):
    app, client = v2_client
    with session_mod.SessionLocal() as s:
        run = svc.create_run(
            s,
            user_id="local",
            session_id=None,
            department="equity_research",
            template_id="stock_research_v2",
            template_raw=_bundled_template_raw("stock_research_v2"),
            template_format="yaml",
            composer_inputs={},
        )
        # Leave in STARTED — not paused.
        s.commit()
        run_id = run.id

    app.state.v2_runner_stage_factory = lambda ctx: _FakeRunner([])
    resp = client.post(
        f"/api/departments/equity-research/v2/runs/{run_id}/resume",
        json={"warning_actions": {}, "clarifications": {}, "question_answers": {}},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "not_paused"


def test_resume_404_for_unknown_run(v2_client):
    app, client = v2_client
    app.state.v2_runner_stage_factory = lambda ctx: _FakeRunner([])
    resp = client.post(
        "/api/departments/equity-research/v2/runs/missing/resume",
        json={"warning_actions": {}, "clarifications": {}, "question_answers": {}},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Bundled template loader
# ---------------------------------------------------------------------------


def _bundled_template_raw(name: str) -> str:
    from pathlib import Path

    p = (
        Path(__file__).resolve().parents[3]
        / "core"
        / "src"
        / "openlia"
        / "llm"
        / "runtime"
        / "report_v2"
        / "templates"
        / f"{name}.yaml"
    )
    return p.read_text()
