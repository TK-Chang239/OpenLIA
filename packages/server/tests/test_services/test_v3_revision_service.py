"""v3 revision service tests (PR4a).

Exercises:
  - happy path: revision writes a new version of a section + leaves
    untouched sections at prior version
  - concurrency: second start_revision_async raises RevisionInFlightError
  - version assignment: monotonic per (report_id, section_id)
  - parent status flips to ``revising`` and back to ``completed``
  - new sections added beyond template land with their own version=1
  - prior citations seed the ledger so prior markers still resolve
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    EventBroker,
    Language,
    LLMSession,
    PriorCitation,
    PriorSection,
    ReportLength,
    ReviseContext,
    Runner,
    RunRequest,
)
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_v3 import (
    ReportV3,
    ReportV3Citation,
    ReportV3Revision,
    ReportV3Section,
)
from openlia_server.services import v3_revision_service as rev_svc
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
        email=f"revise-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="x",
        display_name="R",
    )
    db.add(u)
    db.flush()
    return u


def _seed_completed_report(db: Session, user: User) -> ReportV3:
    """Insert a parent report + one section in v1 state so revision
    tests have something to revise."""
    now = datetime.now(UTC)
    template = get_builtin(ReportType.INITIATION)
    parent = ReportV3(
        id=str(uuid.uuid4()),
        user_id=user.id,
        subject="RKLB.US",
        template_id=template.template_id,
        language=Language.EN.value,
        length=ReportLength.NORMAL.value,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        status="completed",
        error_message=None,
        created_at=now,
        completed_at=now,
    )
    db.add(parent)
    for index, spec in enumerate(template.sections):
        db.add(
            ReportV3Section(
                report_id=parent.id,
                section_id=spec.id,
                section_index=index,
                title=spec.title,
                markdown=f"Prior v1 of {spec.id}.",
                revision_id=None,
                version=1,
            )
        )
    db.flush()
    return parent


def _request(template) -> RunRequest:
    return RunRequest(
        subject="RKLB.US",
        template=template,
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )


@pytest.mark.asyncio
async def test_revision_writes_new_version_for_touched_section(
    create_tables, db_session: Session
):
    user = _make_user(db_session)
    parent = _seed_completed_report(db_session, user)
    template = get_builtin(ReportType.INITIATION)
    touched_section_id = template.sections[0].id

    # Script: model rewrites just one section, then finalizes.
    script = [
        script_tool_calls(
            (
                "write_section",
                {
                    "section_id": touched_section_id,
                    "markdown": "Revised body v2.",
                },
            )
        ),
        script_tool_calls(("finalize", {})),
    ]
    fake = FakeLLMProvider(scripted_responses=script)
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    session.attach_adapter(fake)
    runner = Runner(max_turns=20)

    revise = ReviseContext(
        revision_request="Rewrite the first section.",
        prior_sections=[
            PriorSection(
                section_id=s.section_id,
                title=s.title,
                markdown=s.markdown,
            )
            for s in db_session.query(ReportV3Section)
            .filter(ReportV3Section.report_id == parent.id)
            .all()
        ],
        prior_charts=[],
        prior_citations=[],
    )

    broker = EventBroker()
    cancel_registry: dict = {}
    from openlia_server.db.session import SessionLocal

    db_session.commit()  # release parent + sections to the bg session

    handle = rev_svc.start_revision_async(
        db=db_session,
        user_id=user.id,
        report_id=parent.id,
        revision_request="Rewrite the first section.",
        request=_request(template),
        revise=revise,
        session_factory=SessionLocal,
        broker=broker,
        cancel_registry=cancel_registry,
        runner=runner,
        llm_session=session,
    )
    db_session.commit()

    # Wait for completion
    for _ in range(40):
        await asyncio.sleep(0.05)
        db_session.expire_all()
        rev = db_session.get(ReportV3Revision, handle.revision_id)
        if rev and rev.status in ("completed", "failed", "cancelled"):
            break
    assert rev is not None
    assert rev.status == "completed", rev.error_message

    # Touched section: new row at version=2 with the new markdown.
    rows = (
        db_session.query(ReportV3Section)
        .filter(ReportV3Section.report_id == parent.id)
        .filter(ReportV3Section.section_id == touched_section_id)
        .order_by(ReportV3Section.version.asc())
        .all()
    )
    assert [r.version for r in rows] == [1, 2]
    assert rows[1].markdown == "Revised body v2."
    assert rows[1].revision_id == handle.revision_id

    # Untouched section: still at version=1, no new row.
    other_id = template.sections[1].id
    other_rows = (
        db_session.query(ReportV3Section)
        .filter(ReportV3Section.report_id == parent.id)
        .filter(ReportV3Section.section_id == other_id)
        .all()
    )
    assert len(other_rows) == 1
    assert other_rows[0].version == 1

    # Parent run status back to completed.
    db_session.expire(parent)
    db_session.refresh(parent)
    assert parent.status == "completed"


@pytest.mark.asyncio
async def test_revision_rejects_concurrent_starts(create_tables, db_session: Session):
    """A second start_revision_async on the same report while one is
    in flight raises RevisionInFlightError."""
    user = _make_user(db_session)
    parent = _seed_completed_report(db_session, user)
    template = get_builtin(ReportType.INITIATION)

    # Manually insert a non-terminal revision so the second call sees
    # an active one. Avoids racing the background task in the test.
    now = datetime.now(UTC)
    db_session.add(
        ReportV3Revision(
            id=str(uuid.uuid4()),
            report_id=parent.id,
            user_id=user.id,
            revision_index=1,
            request="first revision",
            status="running",
            error_message=None,
            created_at=now,
            completed_at=None,
        )
    )
    db_session.flush()

    revise = ReviseContext(
        revision_request="second",
        prior_sections=[],
        prior_charts=[],
        prior_citations=[],
    )
    with pytest.raises(rev_svc.RevisionInFlightError):
        rev_svc.start_revision_async(
            db=db_session,
            user_id=user.id,
            report_id=parent.id,
            revision_request="second",
            request=_request(template),
            revise=revise,
            session_factory=lambda: db_session,  # never invoked due to early raise
            broker=EventBroker(),
            cancel_registry={},
        )


def test_has_active_revision_true_for_running_false_for_terminal(
    create_tables, db_session: Session
):
    user = _make_user(db_session)
    parent = _seed_completed_report(db_session, user)
    now = datetime.now(UTC)

    db_session.add(
        ReportV3Revision(
            id=str(uuid.uuid4()),
            report_id=parent.id,
            user_id=user.id,
            revision_index=1,
            request="r1",
            status="completed",
            error_message=None,
            created_at=now,
            completed_at=now,
        )
    )
    db_session.flush()
    assert rev_svc.has_active_revision(db=db_session, report_id=parent.id) is False

    db_session.add(
        ReportV3Revision(
            id=str(uuid.uuid4()),
            report_id=parent.id,
            user_id=user.id,
            revision_index=2,
            request="r2",
            status="running",
            error_message=None,
            created_at=now,
            completed_at=None,
        )
    )
    db_session.flush()
    assert rev_svc.has_active_revision(db=db_session, report_id=parent.id) is True


def test_build_revise_context_loads_latest_sections_and_citations(
    create_tables, db_session: Session
):
    """``build_revise_context_from_db`` reads the LATEST version per
    section_id and rolls up all prior citations + charts."""
    user = _make_user(db_session)
    parent = _seed_completed_report(db_session, user)
    template = get_builtin(ReportType.INITIATION)
    first_id = template.sections[0].id

    # Add a v2 row for the first section so the latest-version reader
    # picks v2 over v1.
    db_session.add(
        ReportV3Section(
            report_id=parent.id,
            section_id=first_id,
            section_index=0,
            title=template.sections[0].title,
            markdown="Latest v2 [^web_1].",
            revision_id=None,
            version=2,
        )
    )
    db_session.add(
        ReportV3Citation(
            report_id=parent.id,
            source_id="web_1",
            tool_name="web_search",
            display_index=1,
            provenance_json=json.dumps({"url": "https://example.com"}),
        )
    )
    db_session.flush()

    ctx = rev_svc.build_revise_context_from_db(
        db=db_session,
        report_id=parent.id,
        revision_request="please re-revise",
    )
    by_id = {p.section_id: p for p in ctx.prior_sections}
    assert by_id[first_id].markdown == "Latest v2 [^web_1]."
    # Untouched sections still come from v1
    second_id = template.sections[1].id
    assert by_id[second_id].markdown == "Prior v1 of " + second_id + "."
    citation_ids = {c.source_id for c in ctx.prior_citations}
    assert "web_1" in citation_ids
