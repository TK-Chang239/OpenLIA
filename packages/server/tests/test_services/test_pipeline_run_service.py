"""Tests for the pipeline_run service layer (Step 2)."""

from __future__ import annotations

from openlia_server.services import pipeline_run_service as svc


def _create_run(db_session, user):
    return svc.create_run(
        db_session,
        user_id=user.id,
        session_id=None,
        department="equity_research",
        template_id="stock_research_v2",
        template_raw="template_id: stock_research_v2\n",
        template_format="yaml",
        composer_inputs={"ticker": "AAPL"},
    )


def test_create_run_persists_started_state(db_session, make_user):
    user = make_user()
    run = _create_run(db_session, user)

    assert run.id
    assert run.state == "STARTED"
    assert run.composer_inputs == {"ticker": "AAPL"}
    assert run.clarification_history == []
    assert run.paused_at is None
    assert run.completed_at is None


def test_mark_paused_records_clarifier_output(db_session, make_user):
    user = make_user()
    run = _create_run(db_session, user)

    clarifier_output = {
        "questions": [],
        "blocking_warnings": [
            {
                "capability_id": "extra_passes",
                "detected_phrase": "devil's advocate",
                "user_message": "msg",
                "available_actions": ["proceed_without", "cancel_and_edit", "clarify"],
            }
        ],
        "notices": [],
        "detected_intents": ["extra_passes"],
    }
    paused = svc.mark_paused(
        db_session,
        run.id,
        stage="clarify",
        clarifier_output=clarifier_output,
        clarifier_round=1,
        clarification_history=[clarifier_output],
    )

    assert paused.state == "CLARIFY_AWAITING_USER"
    assert paused.paused_at_stage == "clarify"
    assert paused.last_clarifier_output == clarifier_output
    assert paused.last_clarifier_round == 1
    assert paused.clarification_history == [clarifier_output]
    assert paused.paused_at is not None


def test_mark_running_clears_paused_stage(db_session, make_user):
    user = make_user()
    run = _create_run(db_session, user)
    svc.mark_paused(
        db_session,
        run.id,
        stage="clarify",
        clarifier_output={},
        clarifier_round=1,
        clarification_history=[],
    )

    resumed = svc.mark_running(db_session, run.id)

    assert resumed.state == "RUNNING"
    assert resumed.paused_at_stage is None


def test_mark_completed_sets_completed_at(db_session, make_user):
    user = make_user()
    run = _create_run(db_session, user)

    finished = svc.mark_completed(db_session, run.id)

    assert finished.state == "COMPLETED"
    assert finished.completed_at is not None


def test_mark_completed_degraded_sets_degraded_state(db_session, make_user):
    user = make_user()
    run = _create_run(db_session, user)

    finished = svc.mark_completed(db_session, run.id, degraded=True)

    assert finished.state == "DEGRADED"
    assert finished.completed_at is not None


def test_mark_failed_records_reason(db_session, make_user):
    user = make_user()
    run = _create_run(db_session, user)

    failed = svc.mark_failed(db_session, run.id, reason="planner blew up")

    assert failed.state == "FAILED"
    assert failed.failure_reason == "planner blew up"
    assert failed.completed_at is not None


def test_get_run_returns_none_for_unknown(db_session):
    assert svc.get_run(db_session, "missing-id") is None
