"""Phase 3b-backend server-side tests.

Exercises:
  - start_run_async creates the Report row + returns immediately + the
    background task eventually finishes and persists outcome
  - cancel_run flips the registered token; runner exits and the row
    lands at status='failed'
  - cleanup_orphaned_running_rows converts stale 'running' rows on
    startup
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    DataTransports,
    EventBroker,
    Language,
    LLMSession,
    ReportLength,
    Runner,
    RunRequest,
)
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_v3 import ReportV3
from openlia_server.services import v3_run_service as svc
from sqlalchemy.orm import Session

_CORE_TEST_DIR = (
    Path(__file__).resolve().parents[3] / "core" / "tests" / "test_runtime" / "test_report_v3"
)
sys.path.insert(0, str(_CORE_TEST_DIR.parent.parent.parent / "tests"))
from test_runtime.test_report_v3._fakes import (  # noqa: E402
    FakeLLMProvider,
    script_tool_calls,
)


def _make_user(db: Session) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="stream@test.com",
        password_hash="x",
        display_name="S",
    )
    db.add(u)
    db.flush()
    return u


def _fake_transports() -> DataTransports:
    return DataTransports(
        fundamentals=lambda ticker: {"ticker": ticker},
        prices=lambda ticker, from_date, to_date: [],
        news=lambda ticker, limit: [{"title": "n", "url": f"https://x.test/{ticker}"}],
    )


def _request() -> RunRequest:
    return RunRequest(
        subject="RKLB.US",
        template=get_builtin(ReportType.INITIATION),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )


def _happy_script(req: RunRequest):
    section_ids = [s.id for s in req.template.sections]
    script = [script_tool_calls(("get_company_news", {"ticker": "RKLB.US"}))]
    for sid in section_ids:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} [^eodhd_1]."})
            )
        )
    script.append(script_tool_calls(("finalize", {})))
    return script


@pytest.mark.asyncio
async def test_start_run_async_returns_immediately_and_background_completes(
    create_tables, db_session: Session
):
    user = _make_user(db_session)
    req = _request()

    llm_session = LLMSession.create(
        provider_kind="anthropic", model="claude-sonnet-4-6"
    )
    fake = FakeLLMProvider(scripted_responses=_happy_script(req))
    llm_session.attach_adapter(fake)
    runner = Runner(max_turns=30, transports_factory=_fake_transports)

    broker = EventBroker()
    cancel_registry: dict = {}

    from openlia_server.db.session import SessionLocal

    handle = svc.start_run_async(
        db=db_session,
        user_id=user.id,
        request=req,
        session_factory=SessionLocal,
        broker=broker,
        cancel_registry=cancel_registry,
        runner=runner,
        llm_session=llm_session,
    )
    db_session.commit()  # release the row to the background session

    # Row exists with status='running' before the bg task finishes
    db_session.expire_all()
    row = db_session.get(ReportV3, handle.report_id)
    assert row is not None
    # Background task may or may not have completed by now; wait for it.
    for _ in range(30):
        await asyncio.sleep(0.05)
        db_session.expire(row)
        db_session.refresh(row)
        if row.status != "running":
            break
    assert row.status == "completed"
    assert row.completed_at is not None
    # Cancel token cleaned up after completion
    assert handle.report_id not in cancel_registry


@pytest.mark.asyncio
async def test_cancel_run_aborts_background_with_failed_status(
    create_tables, db_session: Session
):
    user = _make_user(db_session)
    req = _request()

    # Script with many tool calls so we have a window to cancel mid-run.
    script = [script_tool_calls(("get_company_news", {"ticker": "RKLB.US"}))] * 25

    llm_session = LLMSession.create(
        provider_kind="anthropic", model="claude-sonnet-4-6"
    )
    # 50ms per turn so the cancel lands while the runner is still
    # iterating, not after it has exhausted the script.
    fake = FakeLLMProvider(scripted_responses=script, per_call_delay_seconds=0.05)
    llm_session.attach_adapter(fake)
    runner = Runner(max_turns=30, transports_factory=_fake_transports)

    broker = EventBroker()
    cancel_registry: dict = {}

    from openlia_server.db.session import SessionLocal

    handle = svc.start_run_async(
        db=db_session,
        user_id=user.id,
        request=req,
        session_factory=SessionLocal,
        broker=broker,
        cancel_registry=cancel_registry,
        runner=runner,
        llm_session=llm_session,
    )
    db_session.commit()

    # Let the background task get past run.started + one turn before
    # cancelling. With 50ms per turn this lands while the runner
    # is between turns.
    await asyncio.sleep(0.06)
    found = svc.cancel_run(cancel_registry=cancel_registry, report_id=handle.report_id)
    assert found is True

    row = db_session.get(ReportV3, handle.report_id)
    assert row is not None
    for _ in range(50):
        await asyncio.sleep(0.05)
        db_session.expire(row)
        db_session.refresh(row)
        if row.status != "running":
            break
    assert row.status == "failed"
    # Cancel registry purged after the run ended.
    assert handle.report_id not in cancel_registry


def test_cancel_run_returns_false_when_no_token_registered():
    assert svc.cancel_run(cancel_registry={}, report_id="missing") is False


def test_cleanup_orphaned_running_rows_marks_only_running_status(
    create_tables, db_session: Session
):
    user = _make_user(db_session)
    now = datetime.now(UTC)
    db_session.add(
        ReportV3(
            id=str(uuid.uuid4()),
            user_id=user.id,
            subject="A",
            template_id="initiation",
            language="en",
            length="normal",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="running",
            created_at=now - timedelta(minutes=10),
        )
    )
    db_session.add(
        ReportV3(
            id=str(uuid.uuid4()),
            user_id=user.id,
            subject="B",
            template_id="initiation",
            language="en",
            length="normal",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="completed",
            created_at=now - timedelta(minutes=20),
            completed_at=now - timedelta(minutes=15),
        )
    )
    db_session.add(
        ReportV3(
            id=str(uuid.uuid4()),
            user_id=user.id,
            subject="C",
            template_id="initiation",
            language="en",
            length="normal",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="failed",
            error_message="prior failure",
            created_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=25),
        )
    )
    db_session.commit()

    converted = svc.cleanup_orphaned_running_rows(db=db_session)
    assert converted == 1

    statuses = sorted(
        r.status for r in db_session.scalars(
            __import__("sqlalchemy").select(ReportV3).where(ReportV3.user_id == user.id)
        )
    )
    assert statuses == ["completed", "failed", "failed"]
