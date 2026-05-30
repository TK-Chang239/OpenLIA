"""End-to-end backend smoke for the EU v2 scheduled-trigger pipeline.

Proves the whole scheduled path holds together with no network and no
real LLM keys:

    watchlist entry
        -> sync_user_watchlist (fake EODHD calendar, past-dated release)
        -> a DUE eu_v2_earnings_schedule row
        -> EuV2DispatcherImpl.dispatch_due fires a run
        -> the report_eu row persists status="completed", trigger="scheduled"
        -> the schedule row flips to status="reported" with report_id set.

PATH A (full pipeline through ``dispatch_due``) is used.

The only seam needed is the LLM adapter. ``dispatch_due`` calls
``start_run_async`` without a ``session=`` override, so the background
task falls back to ``LLMSession.create(...)`` inside ``eu_v2_run_service``.
We monkeypatch *that* classmethod to hand back a real ``LLMSession`` with a
scripted ``FakeLLMProvider`` already attached -- the exact fake the
run-service test (``test_start_run_async_completes_and_persists``) uses,
just reached one frame deeper because the dispatcher owns session
construction. No production seam was added: the patch targets the test's
view of ``LLMSession.create`` only.

Transports are left to the env-wired -> null fallback. With all three
connectors OFF the catalog is output-tools-only, so the scripted fake
never calls a data tool and the null transports are never touched.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from openlia.llm.runtime.report_eu import LLMSession
from openlia.llm.runtime.report_eu.default_template import build_default_template
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_eu import (
    EuV2EarningsSchedule,
    ReportEu,
    ReportEuSection,
    ReportEuTemplate,
)
from openlia_server.services import eu_v2_run_service
from openlia_server.services.eu_v2_calendar_sync import sync_user_watchlist
from openlia_server.services.eu_v2_scheduler_impl import EuV2DispatcherImpl
from openlia_server.services.eu_v2_settings import update_settings
from openlia_server.services.eu_v2_watchlist import add_entry
from sqlalchemy import select

# Pull the report_eu FakeLLMProvider helpers from the core test tree,
# the same way test_eu_v2_run_service.py does.
_CORE_TESTS = Path(__file__).resolve().parents[3] / "core" / "tests"
sys.path.insert(0, str(_CORE_TESTS))
from runtime.report_eu._fakes import (  # noqa: E402
    FakeLLMProvider,
    script_tool_calls,
)


def _seed_user(db, user_id: str = "u-1") -> None:
    if db.get(User, user_id) is None:
        now = datetime.now(UTC)
        db.add(
            User(
                id=user_id,
                email=f"{user_id}@test.example",
                display_name=user_id,
                password_hash=None,
                is_admin=False,
                is_disabled=False,
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()


def _seed_eu_default(db) -> None:
    spec = build_default_template()
    now = datetime.now(UTC)
    db.add(
        ReportEuTemplate(
            id=spec.template_id,
            user_id=None,
            name=spec.name,
            is_builtin=True,
            template_spec_json=json.loads(spec.model_dump_json()),
            source_markdown=None,
            source_doc_blob=None,
            source_doc_mime=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
    )
    db.flush()


# Capture the genuine classmethod up front so the monkeypatched seam can
# still build a real session without re-entering the patch (recursion).
_REAL_SESSION_CREATE = LLMSession.create


def _make_fake_session() -> LLMSession:
    """A real LLMSession with a scripted fake adapter attached.

    Scripts: write all eu_default sections (connectors off, so no data
    tools), then finalize -- identical to the run-service test's fake.
    """
    section_ids = [s.id for s in build_default_template().sections]
    script = [
        script_tool_calls(("write_section", {"section_id": sid, "markdown": f"{sid} body."}))
        for sid in section_ids
    ]
    script.append(script_tool_calls(("finalize", {})))
    session = _REAL_SESSION_CREATE(provider_kind="anthropic", model="claude-sonnet-4-6")
    session.attach_adapter(FakeLLMProvider(scripted_responses=script))
    return session


@pytest.mark.asyncio
async def test_scheduled_run_completes_and_marks_reported(
    db_session, db_session_factory, monkeypatch
):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    _seed_user(db_session)
    _seed_eu_default(db_session)
    db_session.commit()

    # 1. Settings: all three connectors OFF -> output-tools-only catalog,
    #    so the fake session writes from the prompt alone. Defaults kept
    #    for provider/model.
    update_settings(
        db_session,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        financial_enabled=False,
        calendar_enabled=False,
        web_search_enabled=False,
    )

    # 2. Watchlist ticker.
    add_entry(db_session, user_id="u-1", ticker="MSFT.US", company_name=None)

    # 3. Drive the real sync path with a fake EODHD calendar that returns a
    #    PAST-dated release, producing a DUE pending schedule row.
    now = datetime.now(UTC)
    past_release_date = (now - timedelta(days=2)).date().isoformat()

    def _fake_calendar(ticker: str) -> list[dict]:
        assert ticker == "MSFT.US"
        return [
            {
                "report_date": past_release_date,
                "before_after_market": "AfterMarket",
                "estimate": 2.50,
                "revenue_estimate_avg": 65_000_000_000,
            }
        ]

    touched = sync_user_watchlist(
        db_session, user_id="u-1", earnings_calendar=_fake_calendar, now=now
    )
    assert touched == 1

    pending = db_session.scalars(
        select(EuV2EarningsSchedule).where(EuV2EarningsSchedule.user_id == "u-1")
    ).all()
    assert len(pending) == 1
    schedule_id = pending[0].id
    assert pending[0].status == "pending"
    assert pending[0].scheduled_run_at <= now  # genuinely due

    # 4. Inject the fake LLM session at the seam the dispatcher reaches:
    #    ``start_run_async`` passes session=None, so the background task
    #    builds one via ``LLMSession.create`` -- patch that to return our
    #    scripted fake. (No production override seam added.)
    monkeypatch.setattr(
        eu_v2_run_service.LLMSession,
        "create",
        classmethod(lambda cls, **_kw: _make_fake_session()),
    )

    # 5. Fire the dispatcher with ``now`` past the scheduled run time.
    dispatcher = EuV2DispatcherImpl(session_factory=db_session_factory)
    fired = dispatcher.dispatch_due(session=db_session, now=now)
    assert fired == 1

    # The runner is a background asyncio task on this loop; await it.
    for _ in range(500):
        if not eu_v2_run_service._BACKGROUND_TASKS:
            break
        await asyncio.sleep(0.01)
    assert not eu_v2_run_service._BACKGROUND_TASKS, "background run task never finished"

    # 6. Report persisted completed, scheduled trigger, >=1 section.
    with db_session_factory() as check:
        schedule_row = check.get(EuV2EarningsSchedule, schedule_id)
        assert schedule_row is not None
        report_id = schedule_row.report_id
        assert report_id is not None

        report = check.get(ReportEu, report_id)
        assert report is not None
        assert report.status == "completed"
        assert report.trigger_kind == "scheduled"
        assert report.ticker == "MSFT.US"
        assert report.fiscal_date == past_release_date

        sections = list(
            check.scalars(select(ReportEuSection).where(ReportEuSection.report_id == report_id))
        )
        assert len(sections) >= 1

        # 7. Schedule row flipped to reported, anchored to that report.
        assert schedule_row.status == "reported"
        assert schedule_row.report_id == report_id
