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
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])))

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
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])))

    start = client.post("/api/departments/equity-research/v2.3/runs", json=_start_payload())
    run_id = start.json()["run_id"]

    resp = client.post(
        f"/api/departments/equity-research/v2.3/runs/{run_id}/answer",
        json={"answers": {}},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "invalid_run_state"


# ---------------------------------------------------------------------------
# Task 4 (Phase 1.5): upload-then-launch end-to-end
# ---------------------------------------------------------------------------


def test_v23_run_uses_user_uploaded_template_end_to_end(v2_3_client) -> None:
    """Parse markdown -> save as a report_templates row -> launch a run
    with that template_id -> confirm the persisted ReportState carries
    the user's template (proves the upload-then-launch wiring end-to-end).
    """
    app, client = v2_3_client
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed(assumptions=["audience: PM"])))

    # 1. Parse markdown via the v2.3 endpoint.
    parse_resp = client.post(
        "/api/report-templates/v23/parse",
        json={
            "markdown": (
                "<!-- openlia\nname: My initiation template\n-->\n"
                "# Overview\nWhat the company does.\n\n"
                "# Recommendation\nFinal stance.\n"
            ),
            "name": "My initiation template",
        },
    )
    assert parse_resp.status_code == 200, parse_resp.text
    parse_body = parse_resp.json()
    assert parse_body["validation_errors"] == []
    spec = parse_body["template_spec"]

    # 2. Save via the existing CRUD endpoint.
    save_resp = client.post(
        "/api/report-templates",
        json={
            "name": "My initiation template",
            "template_spec": spec,
            "source_markdown": None,
        },
    )
    assert save_resp.status_code == 201, save_resp.text
    template_row_id = save_resp.json()["id"]

    # 3. Launch a v2.3 run with that template_id.
    run_resp = client.post(
        "/api/departments/equity-research/v2.3/runs",
        json={**_start_payload(), "template_id": template_row_id},
    )
    assert run_resp.status_code == 200, run_resp.text
    started = run_resp.json()
    run_id = started["run_id"]
    # The route's RunStateOut exposes template_id; round-trip proves the
    # selector reached the runner.
    assert started["template_id"] == template_row_id

    # 4. Fetch the run state via GET and confirm the same.
    state_resp = client.get(f"/api/departments/equity-research/v2.3/runs/{run_id}")
    assert state_resp.status_code == 200, state_resp.text
    assert state_resp.json()["template_id"] == template_row_id

    # 5. Load the persisted ReportState from the DB and confirm
    # `state.template` carries the user's uploaded template — not the
    # built-in for `initiation`. This is the load-bearing assertion: the
    # service layer resolved the row, validated it as a v2.3 TemplateSpec,
    # and bound it to `state.template`.
    from openlia.llm.runtime.report_v2_3.persistence import StateStore  # noqa: F401
    from openlia_server.db import session as session_mod
    from openlia_server.services.v2_3_state_store import SqlStateStore

    with session_mod.SessionLocal() as s:
        persisted = SqlStateStore(s).load(run_id)
    assert persisted.template.name == "My initiation template"
    assert [sec.id for sec in persisted.template.sections] == [
        "overview",
        "recommendation",
    ]


def test_v23_built_in_initiation_resolves_to_initiation_default(v2_3_client) -> None:
    """report_type=initiation + template_id=None should land state.template
    on the Stock Initiation built-in."""
    _assert_builtin_resolves(v2_3_client, "initiation", "initiation_default", "Stock Initiation")


def test_v23_built_in_update_resolves_to_update_default(v2_3_client) -> None:
    _assert_builtin_resolves(v2_3_client, "update", "update_default", "Stock Update")


def test_v23_built_in_sector_research_resolves_to_sector_research_default(
    v2_3_client,
) -> None:
    _assert_builtin_resolves(
        v2_3_client, "sector_research", "sector_research_default", "Sector Research"
    )


def _assert_builtin_resolves(
    v2_3_client, report_type: str, expected_template_id: str, expected_name: str
) -> None:
    """Helper: start a run with the given report_type and no template_id,
    then load the persisted ReportState and confirm state.template binds
    to the matching built-in."""
    app, client = v2_3_client
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed(assumptions=["x"])))
    payload = {**_start_payload(), "report_type": report_type}
    # Sector research is thematic, no ticker required.
    if report_type == "sector_research":
        payload["tickers"] = []
    resp = client.post("/api/departments/equity-research/v2.3/runs", json=payload)
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]

    from openlia_server.db import session as session_mod
    from openlia_server.services.v2_3_state_store import SqlStateStore

    with session_mod.SessionLocal() as s:
        persisted = SqlStateStore(s).load(run_id)
    assert persisted.template.template_id == expected_template_id
    assert persisted.template.name == expected_name
    # template_id (the user-template-row column) stays None because the
    # run selected a built-in.
    assert persisted.template_id is None


def test_v23_run_returns_404_for_other_users_template(v2_3_client) -> None:
    """The cross-owner integration seam: a template_id that exists but
    belongs to a different user must surface as 404 at the route layer
    (no existence leak). Guards against accidental drop of `user_id`
    plumbing in `_resolve_template`."""
    app, client = v2_3_client
    _install_factory(app, FakeClarifierClient(result=ClarifyProceed(assumptions=["audience: PM"])))

    # Seed a second user and a template owned by them.
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.report_templates import ReportTemplate

    with session_mod.SessionLocal() as s:
        s.add(
            User(
                id="other-user",
                email="other@openlia.local",
                display_name="Other",
                is_admin=False,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.add(
            ReportTemplate(
                id="other-template-uuid",
                user_id="other-user",
                name="Other user's template",
                template_spec_json={
                    "template_id": "other_template_abcd1234",
                    "name": "Other user's template",
                    "shape_description": "Owned by another user.",
                    "ticker_anchored": True,
                    "sections": [
                        {
                            "id": "primer",
                            "title": "Primer",
                            "intent": "Set up.",
                            "methodology_hints": [],
                        }
                    ],
                },
            )
        )
        s.commit()

    # The default "local" user tries to launch a run pointing at the
    # other user's template. Route-level _resolve_template must reject.
    run_resp = client.post(
        "/api/departments/equity-research/v2.3/runs",
        json={**_start_payload(), "template_id": "other-template-uuid"},
    )
    assert run_resp.status_code == 404, run_resp.text
