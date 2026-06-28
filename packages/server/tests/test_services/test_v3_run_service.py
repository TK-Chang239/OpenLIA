"""Phase 2a tests for the v3 run service + persistence.

Exercises:
  - start_run persists 5-table outcome on a happy-path run with
    FakeLLMProvider scripting tool calls.
  - get_run returns the full denormalized view.
  - list_runs respects user scoping + status filter.
  - delete_run cascades child rows.
  - Citations get assigned display_index in body order, deduped by
    source_id (first appearance wins).
  - Capability gate failure persists status="failed".

No live API calls; FakeLLMProvider drives the loop deterministically.
"""

from __future__ import annotations

import json

# Pull the FakeLLMProvider helpers from the core test package by
# adding its dir to the path. Server tests live in a different tree.
import sys
import uuid
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    CapabilityError,
    DataTransports,
    Language,
    LLMSession,
    ReportLength,
    Runner,
    RunRequest,
)
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_v3 import (
    ReportV3,
    ReportV3Chart,
    ReportV3Citation,
    ReportV3Section,
    ReportV3ToolCallLog,
)
from openlia_server.services import v3_run_service as svc
from sqlalchemy import select
from sqlalchemy.orm import Session

_CORE_TEST_DIR = (
    Path(__file__).resolve().parents[3] / "core" / "tests" / "test_runtime" / "test_report_v3"
)
sys.path.insert(0, str(_CORE_TEST_DIR.parent.parent.parent / "tests"))
from test_runtime.test_report_v3._fakes import (  # noqa: E402
    FakeLLMProvider,
    script_tool_calls,
)

# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


def _make_user(db: Session) -> User:
    u = User(id=str(uuid.uuid4()), email="v3@test.com", password_hash="x", display_name="V3")
    db.add(u)
    db.flush()
    return u


def _request() -> RunRequest:
    return RunRequest(
        subject="RKLB.US",
        template=get_builtin(ReportType.INITIATION),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )


def _fake_transports() -> DataTransports:
    """Trivial transports that return canned data so EODHD tools succeed."""
    return DataTransports(
        fundamentals=lambda ticker: {"ticker": ticker, "ok": True},
        prices=lambda ticker, from_date, to_date: [
            {"date": from_date, "close": 1.0},
            {"date": to_date, "close": 2.0},
        ],
        news=lambda ticker, limit: [{"title": "headline", "url": f"https://x.test/{ticker}"}],
    )


def _runner_with(responses) -> tuple[Runner, LLMSession]:
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    fake = FakeLLMProvider(scripted_responses=responses)
    session.attach_adapter(fake)
    runner = Runner(max_turns=20, transports_factory=_fake_transports)
    return runner, session


def _happy_path_script(req: RunRequest, *, with_chart: bool = False) -> list:
    """Script: one EODHD call, optional chart, write every section, finalize."""
    section_ids = [s.id for s in req.template.sections]
    script = []
    script.append(script_tool_calls(("get_company_news", {"ticker": "RKLB.US"})))
    if with_chart:
        script.append(
            script_tool_calls(
                (
                    "emit_chart",
                    {
                        "chart_id": "trend",
                        "chart_type": "line",
                        "title": "Trend",
                        "data": [{"x": "2024", "y": 1.0}, {"x": "2025", "y": 2.0}],
                        "source_ids": ["eodhd_1"],
                    },
                )
            )
        )
    for sid in section_ids:
        script.append(
            script_tool_calls(
                (
                    "write_section",
                    {"section_id": sid, "markdown": f"{sid} body [^eodhd_1]."},
                )
            )
        )
    script.append(script_tool_calls(("finalize", {})))
    return script


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_run_persists_all_five_tables(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = _request()
    runner, session = _runner_with(_happy_path_script(req, with_chart=True))

    outcome = await svc.start_run(
        db=db_session,
        user_id=user.id,
        request=req,
        runner=runner,
        session=session,
    )
    db_session.flush()

    # Report row
    row = db_session.get(ReportV3, outcome.report_id)
    assert row is not None
    assert row.user_id == user.id
    assert row.status == "completed"
    assert row.subject == "RKLB.US"
    assert row.completed_at is not None

    # Sections — every template section persisted in template order
    sections = list(
        db_session.scalars(
            select(ReportV3Section)
            .where(ReportV3Section.report_id == outcome.report_id)
            .order_by(ReportV3Section.section_index)
        )
    )
    expected_section_ids = [s.id for s in req.template.sections]
    assert [s.section_id for s in sections] == expected_section_ids
    assert all(s.markdown.endswith("[^eodhd_1].") for s in sections)

    # Chart persisted
    charts = list(
        db_session.scalars(
            select(ReportV3Chart).where(ReportV3Chart.report_id == outcome.report_id)
        )
    )
    assert len(charts) == 1
    assert charts[0].chart_id == "trend"
    assert charts[0].rendered_url is None  # Phase 2b fills this
    assert json.loads(charts[0].spec_json)["chart_id"] == "trend"

    # Citations — one per source_id, eodhd_1 gets display_index=1
    citations = list(
        db_session.scalars(
            select(ReportV3Citation).where(ReportV3Citation.report_id == outcome.report_id)
        )
    )
    by_source = {c.source_id: c for c in citations}
    assert "eodhd_1" in by_source
    assert by_source["eodhd_1"].display_index == 1

    # Tool call log — at least the EODHD call landed
    log_rows = list(
        db_session.scalars(
            select(ReportV3ToolCallLog).where(ReportV3ToolCallLog.report_id == outcome.report_id)
        )
    )
    assert any(r.tool_name == "get_company_news" for r in log_rows)


@pytest.mark.asyncio
async def test_capability_error_persists_failed_status(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = RunRequest(
        subject="RKLB.US",
        template=get_builtin(ReportType.INITIATION),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="ollama",
        model="llama3.1",
    )
    with pytest.raises(CapabilityError):
        await svc.start_run(db=db_session, user_id=user.id, request=req)

    db_session.flush()
    rows = list(db_session.scalars(select(ReportV3).where(ReportV3.user_id == user.id)))
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert "web search" in (rows[0].error_message or "").lower()


@pytest.mark.asyncio
async def test_async_capability_error_marks_row_failed(
    create_tables, db_session: Session, db_session_factory
):
    """The async path must commit the row before the background task runs, so a
    fast CapabilityError is recorded as status='failed' — not left invisible to
    the background session (which leaves the run stuck on 'running' forever)."""
    import asyncio

    from openlia.llm.runtime.report_v3 import EventBroker

    user = _make_user(db_session)
    db_session.commit()
    req = RunRequest(
        subject="RKLB.US",
        template=get_builtin(ReportType.INITIATION),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="ollama",
        model="llama3.1",
    )

    handle = svc.start_run_async(
        db=db_session,
        user_id=user.id,
        request=req,
        session_factory=db_session_factory,
        broker=EventBroker(),
        cancel_registry={},
    )
    await asyncio.gather(*list(svc._BACKGROUND_TASKS))

    with db_session_factory() as fresh:
        row = fresh.get(ReportV3, handle.report_id)
        assert row is not None
        assert row.status == "failed"
        assert "web search" in (row.error_message or "").lower()


@pytest.mark.asyncio
async def test_start_run_resolves_and_forwards_capability_override(create_tables, db_session):
    """start_run must look up the per-model capability override from the DB and
    thread it into runner.run, so admins can enable a new model without code."""
    from openlia_server.services.llm_providers import set_capability_override

    user = _make_user(db_session)
    set_capability_override(
        db_session,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        override={"web_search_native": False},
    )
    db_session.commit()

    class _Recorder:
        def __init__(self) -> None:
            self.capability_override: object = "UNSET"

        async def run(
            self,
            request,
            *,
            session=None,
            emitter=None,
            cancel_token=None,
            revise=None,
            capability_override=None,
        ):
            self.capability_override = capability_override
            raise CapabilityError("stop after capture")

    recorder = _Recorder()
    with pytest.raises(CapabilityError):
        await svc.start_run(db=db_session, user_id=user.id, request=_request(), runner=recorder)

    assert recorder.capability_override == {"web_search_native": False}


@pytest.mark.asyncio
async def test_get_run_returns_full_denormalized_view(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = _request()
    runner, session = _runner_with(_happy_path_script(req))

    outcome = await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner, session=session
    )
    db_session.flush()

    row, sections, charts, citations = svc.get_run(
        db=db_session, user_id=user.id, report_id=outcome.report_id
    )
    assert row.id == outcome.report_id
    assert [s.section_index for s in sections] == list(range(len(sections)))
    assert charts == []  # no chart in this script
    assert any(c.source_id == "eodhd_1" for c in citations)


@pytest.mark.asyncio
async def test_get_run_rejects_other_users_report(create_tables, db_session: Session):
    owner = _make_user(db_session)
    intruder = User(
        id=str(uuid.uuid4()),
        email="other@test.com",
        password_hash="x",
        display_name="Other",
    )
    db_session.add(intruder)
    db_session.flush()
    req = _request()
    runner, session = _runner_with(_happy_path_script(req))
    outcome = await svc.start_run(
        db=db_session, user_id=owner.id, request=req, runner=runner, session=session
    )
    with pytest.raises(svc.ReportNotFoundError):
        svc.get_run(db=db_session, user_id=intruder.id, report_id=outcome.report_id)


@pytest.mark.asyncio
async def test_list_runs_filters_by_user_and_status(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = _request()
    runner1, session1 = _runner_with(_happy_path_script(req))
    runner2, session2 = _runner_with(_happy_path_script(req))
    await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner1, session=session1
    )
    await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner2, session=session2
    )
    db_session.flush()

    all_runs = svc.list_runs(db=db_session, user_id=user.id)
    assert len(all_runs) == 2
    completed = svc.list_runs(db=db_session, user_id=user.id, status="completed")
    assert len(completed) == 2
    failed = svc.list_runs(db=db_session, user_id=user.id, status="failed")
    assert failed == []


@pytest.mark.asyncio
async def test_delete_run_cascades_to_children(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = _request()
    runner, session = _runner_with(_happy_path_script(req, with_chart=True))
    outcome = await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner, session=session
    )
    db_session.flush()

    svc.delete_run(db=db_session, user_id=user.id, report_id=outcome.report_id)
    db_session.flush()

    assert db_session.get(ReportV3, outcome.report_id) is None
    assert (
        list(
            db_session.scalars(
                select(ReportV3Section).where(ReportV3Section.report_id == outcome.report_id)
            )
        )
        == []
    )
    assert (
        list(
            db_session.scalars(
                select(ReportV3Chart).where(ReportV3Chart.report_id == outcome.report_id)
            )
        )
        == []
    )


@pytest.mark.asyncio
async def test_citation_display_index_orders_by_first_appearance(
    create_tables, db_session: Session
):
    """Sources cited only in section 2 must come after sources cited in section 1."""
    user = _make_user(db_session)
    req = _request()
    section_ids = [s.id for s in req.template.sections]

    # Script: two EODHD calls. Section 0 cites eodhd_2 first; section 1
    # cites eodhd_1. Display index must reflect appearance order in
    # the rendered body (which is template order, so eodhd_2 wins
    # index 1 because section 0 is rendered before section 1).
    script = [
        script_tool_calls(("get_company_news", {"ticker": "X"})),
        script_tool_calls(
            (
                "get_historical_prices",
                {"ticker": "X", "from_date": "2024-01-01", "to_date": "2024-12-31"},
            )
        ),
    ]
    markdowns = {
        section_ids[0]: "Cite [^eodhd_2] only.",
        section_ids[1]: "Cite [^eodhd_1] only.",
    }
    for sid in section_ids:
        md = markdowns.get(sid, "body [^eodhd_1].")
        script.append(script_tool_calls(("write_section", {"section_id": sid, "markdown": md})))
    script.append(script_tool_calls(("finalize", {})))

    runner, session = _runner_with(script)
    outcome = await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner, session=session
    )
    db_session.flush()

    citations = list(
        db_session.scalars(
            select(ReportV3Citation).where(ReportV3Citation.report_id == outcome.report_id)
        )
    )
    by_source = {c.source_id: c for c in citations}
    assert by_source["eodhd_2"].display_index == 1
    assert by_source["eodhd_1"].display_index == 2


# ---------------------------------------------------------------------------
# Cover persistence (PR9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_cover_persists_cover_json(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = _request()
    section_ids = [s.id for s in req.template.sections]
    script = [script_tool_calls(("get_company_news", {"ticker": "RKLB.US"}))]
    for sid in section_ids:
        script.append(
            script_tool_calls(
                (
                    "write_section",
                    {"section_id": sid, "markdown": f"{sid} body [^eodhd_1]."},
                )
            )
        )
    script.append(
        script_tool_calls(
            (
                "set_cover",
                {
                    "subtitle": "Q1 2026",
                    "tagline": "Pure-play orbital launch leader",
                    "tldr": ["Backlog at $1.2B", "Neutron on track"],
                    "key_metrics": [
                        {
                            "label": "Revenue FY24",
                            "value": "$436M",
                            "change": "+24% YoY",
                            "tone": "positive",
                        }
                    ],
                    "rating": "Buy",
                    "upside_pct": 28.5,
                },
            )
        )
    )
    script.append(script_tool_calls(("finalize", {})))

    runner, session = _runner_with(script)
    outcome = await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner, session=session
    )
    db_session.flush()

    row = db_session.get(ReportV3, outcome.report_id)
    assert row is not None
    assert row.cover_json is not None
    parsed = json.loads(row.cover_json)
    assert parsed["tagline"] == "Pure-play orbital launch leader"
    assert parsed["rating"] == "Buy"
    assert parsed["upside_pct"] == 28.5
    assert parsed["key_metrics"][0]["tone"] == "positive"


@pytest.mark.asyncio
async def test_run_without_set_cover_leaves_cover_json_null(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = _request()
    # _happy_path_script never calls set_cover; cover_json should stay NULL.
    runner, session = _runner_with(_happy_path_script(req))
    outcome = await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner, session=session
    )
    db_session.flush()

    row = db_session.get(ReportV3, outcome.report_id)
    assert row is not None
    assert row.cover_json is None


# ---------------------------------------------------------------------------
# reasoning_effort persistence (PR12 follow-up)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reasoning_effort_persists_on_report_row(create_tables, db_session: Session):
    from openlia.llm.types import ReasoningEffort

    user = _make_user(db_session)
    req = _request().model_copy(update={"reasoning_effort": ReasoningEffort.HIGH})
    runner, session = _runner_with(_happy_path_script(req))
    outcome = await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner, session=session
    )
    db_session.flush()
    row = db_session.get(ReportV3, outcome.report_id)
    assert row is not None
    assert row.reasoning_effort == "high"


@pytest.mark.asyncio
async def test_reasoning_effort_null_when_request_omits_it(create_tables, db_session: Session):
    user = _make_user(db_session)
    req = _request()  # defaults to reasoning_effort=None
    runner, session = _runner_with(_happy_path_script(req))
    outcome = await svc.start_run(
        db=db_session, user_id=user.id, request=req, runner=runner, session=session
    )
    db_session.flush()
    row = db_session.get(ReportV3, outcome.report_id)
    assert row is not None
    assert row.reasoning_effort is None
