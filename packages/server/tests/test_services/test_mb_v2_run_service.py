"""Tests for the MB v2 run service (request build + insert + persist).

``build_run_request`` is exercised against a schedule-style config + the
builtin ``mb_default`` template. ``start_run_async`` is driven with a
fake ``LLMSession`` (a scripted ``FakeLLMProvider`` adapter) so the
runner's tool-use loop completes deterministically with every connector
off and a null transports bundle — no network, no SDK.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from openlia.llm.runtime.report_mb import (
    BriefingContext,
    ChartSpec,
    CitationLogEntry,
    CoverSpec,
    EnabledConnectors,
    EventBroker,
    Language,
    LLMSession,
    MbDataTransports,
    ReportLength,
    RunRequest,
    RunResult,
)
from openlia.llm.runtime.report_mb.default_template import build_default_template
from openlia_server.db.models.content import RepoItem
from openlia_server.db.models.report_mb import (
    ReportMb,
    ReportMbChart,
    ReportMbCitation,
    ReportMbSection,
    ReportMbTemplate,
    ReportMbToolCallLog,
)
from openlia_server.services import mb_v2_run_service as svc
from sqlalchemy import select

# Pull the report_mb FakeLLMProvider helpers from the core test tree.
_CORE_TESTS = Path(__file__).resolve().parents[3] / "core" / "tests"
sys.path.insert(0, str(_CORE_TESTS))
from runtime.report_mb._fakes import (  # noqa: E402
    FakeLLMProvider,
    script_tool_calls,
)


@pytest.fixture
def macro_dept_reader():
    """Save and restore the process-global macro_research department's reader.

    The department registry is a process-wide singleton; a fake reader set in
    a test must not leak into others. Yields the department so a test can set
    its reader, then restores the original ``_reader`` on teardown.
    """
    from openlia.departments import get_department

    dept = get_department("macro_research")
    assert dept is not None
    original = dept._reader
    try:
        yield dept
    finally:
        dept._reader = original


class _FakeMacroReader:
    def __init__(self, entries):
        self._entries = entries

    def latest_snapshot(self, *, user_id: str, dashboard: str):
        return self._entries.get(dashboard)


def test_resolve_macro_snapshot_populated(macro_dept_reader):
    from datetime import date

    from openlia.macro_research.schemas import SnapshotEntry

    now = datetime.now(UTC)
    macro_dept_reader.set_snapshot_reader(
        _FakeMacroReader(
            {
                "debt_cycle": SnapshotEntry(value="Late Plateau", generated_at=now),
                "four_seasons": SnapshotEntry(value="Summer", generated_at=now),
                "five_forces": SnapshotEntry(value=3, generated_at=now),
            }
        )
    )

    ctx = svc._resolve_macro_snapshot("u-1")

    assert ctx is not None
    assert ctx.debt_cycle_phase == "Late Plateau"
    assert ctx.economic_season == "Summer"
    assert ctx.active_force_count == 3
    assert ctx.as_of == now.date().isoformat()
    assert ctx.as_of == date.today().isoformat()
    assert ctx.has_data() is True


def test_resolve_macro_snapshot_none_when_no_data(macro_dept_reader):
    macro_dept_reader.set_snapshot_reader(_FakeMacroReader({}))

    assert svc._resolve_macro_snapshot("u-1") is None


def _seed_mb_default(db) -> None:
    """Insert the mb_default builtin row, mirroring what the migration does."""
    spec = build_default_template()
    now = datetime.now(UTC)
    db.add(
        ReportMbTemplate(
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


def _seed_user(db, user_id: str = "u-1") -> None:
    from openlia_server.db.models.auth import User

    if db.get(User, user_id) is not None:
        return
    now = datetime.now(UTC)
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@openlia.local",
            display_name=user_id,
            password_hash=None,
            is_admin=True,
            is_disabled=False,
            created_at=now,
            updated_at=now,
        )
    )
    db.flush()


def _seed_schedule(db, *, schedule_id: str = "sched-1", user_id: str = "u-1") -> None:
    """Insert an MbSchedule the report_mb.schedule_id FK can point at."""
    from openlia_server.db.models.scheduler import MbSchedule

    if db.get(MbSchedule, schedule_id) is not None:
        return
    db.add(
        MbSchedule(
            id=schedule_id,
            user_id=user_id,
            time="07:00",
            timezone="America/New_York",
            days_of_week="1,2,3,4,5",
            label="Pre-market briefing",
        )
    )
    db.flush()


@pytest.fixture
def db_session_with_seed(db_session, monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "test-eodhd-key")
    _seed_user(db_session)
    _seed_mb_default(db_session)
    return db_session


def test_build_run_request_from_schedule_config(db_session_with_seed):
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        trigger_kind="scheduled",
        template_id="mb_default",
        instructions_id=None,
        enabled_connectors={"provider_ids": ["eodhd"], "web_search": True},
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        language="en",
        length="normal",
        reasoning_effort=None,
        run_date="2026-06-02",
        schedule_label="Pre-market briefing",
        time_label="07:00",
        timezone="America/New_York",
    )
    assert req.provider_kind == "anthropic"
    assert req.model == "claude-sonnet-4-6"
    # eodhd provider enabled + EODHD available -> eodhd on.
    assert req.enabled_connectors.eodhd is True
    assert req.enabled_connectors.web_search is True
    assert req.template.template_id == "mb_default"
    assert isinstance(req.briefing_context, BriefingContext)
    assert req.briefing_context.run_date == "2026-06-02"
    assert req.briefing_context.schedule_label == "Pre-market briefing"
    assert req.briefing_context.time_label == "07:00"
    assert req.briefing_context.timezone == "America/New_York"
    assert req.subject == "Pre-market briefing - 2026-06-02"


def test_build_run_request_on_demand_defaults_run_date_to_today(db_session_with_seed):
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        trigger_kind="on_demand",
        template_id="mb_default",
        instructions_id=None,
        enabled_connectors={},
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        language="en",
        length="normal",
        reasoning_effort="high",
    )
    from datetime import date

    today = date.today().isoformat()
    assert req.briefing_context.run_date == today
    assert req.subject == f"Morning Briefing - {today}"
    assert req.reasoning_effort is not None
    assert req.reasoning_effort.value == "high"


def test_build_run_request_resolves_selected_instructions(db_session_with_seed):
    from openlia_server.services import mb_v2_instructions_service

    profile = mb_v2_instructions_service.create_instructions_from_upload(
        db=db_session_with_seed,
        user_id="u-1",
        name="My methodology",
        body_text="Lead with the macro print. Quantify everything.",
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        trigger_kind="on_demand",
        template_id="mb_default",
        instructions_id=profile.id,
        enabled_connectors={},
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        language="en",
        length="normal",
        reasoning_effort=None,
    )
    assert req.instructions == "Lead with the macro print. Quantify everything."


def test_build_run_request_freeform_without_instructions_raises(db_session_with_seed):
    with pytest.raises(svc.EmptyBriefError):
        svc.build_run_request(
            db_session_with_seed,
            user_id="u-1",
            trigger_kind="on_demand",
            template_id=svc.MB_FREEFORM_TEMPLATE_ID,
            instructions_id=None,
            enabled_connectors={},
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            language="en",
            length="normal",
            reasoning_effort=None,
        )


def test_build_run_request_freeform_with_instructions(db_session_with_seed):
    from openlia_server.services import mb_v2_instructions_service

    profile = mb_v2_instructions_service.create_instructions_from_upload(
        db=db_session_with_seed,
        user_id="u-1",
        name="Freeform methodology",
        body_text="Write whatever structure best fits the tape.",
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        trigger_kind="on_demand",
        template_id=svc.MB_FREEFORM_TEMPLATE_ID,
        instructions_id=profile.id,
        enabled_connectors={},
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        language="en",
        length="normal",
        reasoning_effort=None,
    )
    assert req.template.template_id == svc.MB_FREEFORM_TEMPLATE_ID
    assert req.template.sections == []
    assert req.instructions == "Write whatever structure best fits the tape."


def test_build_run_request_gates_web_search_off_for_incapable_model(db_session_with_seed):
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        trigger_kind="on_demand",
        template_id="mb_default",
        instructions_id=None,
        enabled_connectors={"provider_ids": ["eodhd"], "web_search": True},
        provider_kind="anthropic",
        model="claude-haiku-4-5-20251001",
        language="en",
        length="normal",
        reasoning_effort=None,
    )
    assert req.enabled_connectors.eodhd is True
    assert req.enabled_connectors.web_search is False


def test_build_run_request_drops_provider_without_validated_connector(db_session_with_seed):
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        trigger_kind="on_demand",
        template_id="mb_default",
        instructions_id=None,
        enabled_connectors={"provider_ids": ["eodhd", "ghost"], "web_search": False},
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        language="en",
        length="normal",
        reasoning_effort=None,
    )
    assert set(req.enabled_connectors.provider_ids) == {"eodhd"}


def _make_request(*, run_date: str = "2026-06-02") -> RunRequest:
    return RunRequest(
        subject=f"Morning Briefing - {run_date}",
        template=build_default_template(),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        reasoning_effort=None,
        enabled_connectors=EnabledConnectors(),
        briefing_context=BriefingContext(run_date=run_date, schedule_label="Pre-market"),
        instructions=None,
    )


def test_insert_report_row_creates_running_row_without_repo_pointer(db_session_with_seed):
    _seed_schedule(db_session_with_seed)
    request = _make_request()
    report_id = svc.insert_report_row(
        db_session_with_seed,
        user_id="u-1",
        request=request,
        trigger_kind="scheduled",
        schedule_id="sched-1",
        instructions_id=None,
    )
    db_session_with_seed.flush()

    row = db_session_with_seed.get(ReportMb, report_id)
    assert row is not None
    assert row.status == "running"
    assert row.trigger_kind == "scheduled"
    assert row.schedule_id == "sched-1"
    assert row.subject == request.subject

    # No repo_items pointer is created on run — briefings list from
    # report_mb directly; a pointer is created only on explicit save
    # (mirroring EU). This keeps scheduled briefings out of the repo.
    pointer = db_session_with_seed.execute(
        select(RepoItem).where(RepoItem.mb_v2_report_id == report_id)
    ).scalar_one_or_none()
    assert pointer is None


def test_persist_result_writes_children_and_completes(db_session_with_seed):
    request = _make_request()
    report_id = svc.insert_report_row(
        db_session_with_seed,
        user_id="u-1",
        request=request,
        trigger_kind="on_demand",
    )
    db_session_with_seed.flush()

    result = RunResult(
        status="completed",
        subject=request.subject,
        template_id="mb_default",
        message="",
        sections=[
            {
                "section_id": "market_wrap",
                "title": "Market Wrap",
                "markdown": "Indices up [^web_1].",
            },
        ],
        charts=[
            ChartSpec(
                chart_id="idx_chart",
                chart_type="line",
                title="Index moves",
                data=[{"label": "SPX", "y": 1.2}],
            )
        ],
        citations=[
            CitationLogEntry(
                source_id="web_1",
                tool_name="web_search",
                arguments={"query": "markets"},
                result_summary="markets summary",
                provenance={"url": "https://example.test"},
                timestamp=datetime.now(UTC),
            )
        ],
        cover=CoverSpec(tagline="Risk-on open", tldr=["SPX +1.2%"]),
    )

    svc.persist_result(db_session_with_seed, report_id=report_id, result=result)
    # Mirror the background-outcome status flip the bg task does after persist.
    row = db_session_with_seed.get(ReportMb, report_id)
    row.status = result.status
    row.completed_at = datetime.now(UTC)
    db_session_with_seed.flush()

    assert row.status == "completed"
    assert row.completed_at is not None
    assert row.cover_json is not None

    sections = list(
        db_session_with_seed.scalars(
            select(ReportMbSection).where(ReportMbSection.report_id == report_id)
        )
    )
    assert [s.section_id for s in sections] == ["market_wrap"]

    charts = list(
        db_session_with_seed.scalars(
            select(ReportMbChart).where(ReportMbChart.report_id == report_id)
        )
    )
    assert [c.chart_id for c in charts] == ["idx_chart"]

    citations = list(
        db_session_with_seed.scalars(
            select(ReportMbCitation).where(ReportMbCitation.report_id == report_id)
        )
    )
    assert len(citations) == 1
    assert citations[0].source_id == "web_1"
    assert citations[0].display_index == 1

    logs = list(
        db_session_with_seed.scalars(
            select(ReportMbToolCallLog).where(ReportMbToolCallLog.report_id == report_id)
        )
    )
    assert len(logs) == 1
    assert logs[0].tool_name == "web_search"


def _fake_session() -> tuple[LLMSession, FakeLLMProvider]:
    """A real LLMSession with a scripted fake adapter attached.

    Scripts: write all mb_default sections (connectors off, so no data
    tools), then finalize.
    """
    section_ids = [s.id for s in build_default_template().sections]
    script = [
        script_tool_calls(("write_section", {"section_id": sid, "markdown": f"{sid} body."}))
        for sid in section_ids
    ]
    script.append(script_tool_calls(("finalize", {})))
    fake = FakeLLMProvider(scripted_responses=script)
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    session.attach_adapter(fake)
    return session, fake


def _null_transports() -> MbDataTransports:
    def _raise(*_a: object, **_k: object) -> object:
        raise RuntimeError("not configured")

    return MbDataTransports(
        quotes=_raise,
        prices=_raise,
        news=_raise,
        economic_calendar=_raise,
        macro_indicators=_raise,
    )


@pytest.mark.asyncio
async def test_start_run_async_completes_and_persists(db_session_with_seed, db_session_factory):
    request = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        trigger_kind="scheduled",
        template_id="mb_default",
        instructions_id=None,
        enabled_connectors={},
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        language="en",
        length="normal",
        reasoning_effort=None,
        run_date="2026-06-02",
        schedule_label="Pre-market briefing",
    )

    _seed_schedule(db_session_with_seed)
    session, _fake = _fake_session()
    broker = EventBroker()
    cancel_registry: dict = {}

    report_id = svc.start_run_async(
        db_session_with_seed,
        user_id="u-1",
        request=request,
        broker=broker,
        cancel_registry=cancel_registry,
        session_factory=db_session_factory,
        trigger_kind="scheduled",
        schedule_id="sched-1",
        transports=_null_transports(),
        session=session,
    )
    db_session_with_seed.commit()

    for _ in range(200):
        if not svc._BACKGROUND_TASKS:
            break
        await asyncio.sleep(0.01)

    with db_session_factory() as check:
        row = check.get(ReportMb, report_id)
        assert row is not None
        assert row.status == "completed"
        assert row.trigger_kind == "scheduled"
        assert row.schedule_id == "sched-1"
        assert row.completed_at is not None

        sections = list(
            check.scalars(select(ReportMbSection).where(ReportMbSection.report_id == report_id))
        )
        assert len(sections) == len(build_default_template().sections)

        # The run does not auto-create a repo pointer (save-on-demand only).
        pointer = check.execute(
            select(RepoItem).where(RepoItem.mb_v2_report_id == report_id)
        ).scalar_one_or_none()
        assert pointer is None


def test_build_run_request_honors_capability_override(db_session_with_seed):
    """Web-search gate must honor the same capability override the session applies.

    Regression for the audit's 1.B.3 finding: _build_enabled_connectors gated web
    search with override-free capabilities_for while start_run_async's session
    honored the override. With the schedule requesting web_search and a model
    that defaults web_search_native=False, a user override enabling it must flip
    the gate on.
    """
    from openlia_server.services.llm_providers import set_capability_override

    def _req():
        return svc.build_run_request(
            db_session_with_seed,
            user_id="u-1",
            trigger_kind="on_demand",
            template_id="mb_default",
            instructions_id=None,
            enabled_connectors={"web_search": True},
            provider_kind="anthropic",
            model="claude-haiku-4-6",
            language="en",
            length="normal",
            reasoning_effort=None,
        )

    assert _req().enabled_connectors.web_search is False

    set_capability_override(
        db_session_with_seed,
        provider_kind="anthropic",
        model="claude-haiku-4-6",
        override={"web_search_native": True},
    )
    assert _req().enabled_connectors.web_search is True
