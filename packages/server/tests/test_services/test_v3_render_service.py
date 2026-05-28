"""Phase 2b server tests for v3_render_service round-trips.

Drives a v3 run via FakeLLMProvider to populate the DB, then asks
``render_html`` to assemble the report. Verifies:
  - HTML contains every persisted section title in template order
  - Citations are rewritten to [^N] using display_index
  - Chart data URLs land on the persisted Chart row's rendered_url
  - Bibliography appears with one entry per cited source
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    DataTransports,
    Language,
    LLMSession,
    ReportLength,
    Runner,
    RunRequest,
)
from openlia_server.db.models.auth import User
from openlia_server.services import v3_render_service as render_svc
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
        email="render@test.com",
        password_hash="x",
        display_name="R",
    )
    db.add(u)
    db.flush()
    return u


def _fake_transports() -> DataTransports:
    return DataTransports(
        fundamentals=lambda ticker: {"ticker": ticker, "ok": True},
        prices=lambda ticker, from_date, to_date: [
            {"date": from_date, "close": 1.0},
            {"date": to_date, "close": 2.0},
        ],
        news=lambda ticker, limit: [{"title": "h", "url": f"https://x.test/{ticker}"}],
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


def _build_full_run_script(req: RunRequest) -> list:
    section_ids = [s.id for s in req.template.sections]
    script = [
        script_tool_calls(("get_company_news", {"ticker": "RKLB.US"})),
        script_tool_calls(
            (
                "emit_chart",
                {
                    "chart_id": "growth",
                    "chart_type": "line",
                    "title": "Growth Trend",
                    "data": [{"x": "2024", "y": 1.0}, {"x": "2025", "y": 2.5}],
                    "source_ids": ["eodhd_1"],
                },
            )
        ),
    ]
    # First section references the chart + cites eodhd_1
    script.append(
        script_tool_calls(
            (
                "write_section",
                {
                    "section_id": section_ids[0],
                    "markdown": (
                        "Strong growth this period [^eodhd_1].\n\n"
                        "{{chart:growth}}\n\n"
                        "Outlook remains positive."
                    ),
                },
            )
        )
    )
    for sid in section_ids[1:]:
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


@pytest.mark.asyncio
async def test_render_html_round_trips_through_persistence(
    create_tables, db_session: Session
):
    user = _make_user(db_session)
    req = _request()

    session = LLMSession.create(
        provider_kind="anthropic", model="claude-sonnet-4-6"
    )
    fake = FakeLLMProvider(scripted_responses=_build_full_run_script(req))
    session.attach_adapter(fake)
    runner = Runner(max_turns=30, transports_factory=_fake_transports)

    outcome = await svc.start_run(
        db=db_session,
        user_id=user.id,
        request=req,
        runner=runner,
        session=session,
    )
    db_session.flush()

    rendered = render_svc.render_html(
        db=db_session, user_id=user.id, report_id=outcome.report_id
    )
    html = rendered.html

    # Cover
    assert "RKLB.US" in html
    assert "Template: initiation" in html

    # Every template section title appears in template order
    template = req.template
    section_titles = [s.title for s in template.sections]
    positions = [html.index(title) for title in section_titles]
    assert positions == sorted(positions), "sections must appear in template order"

    # Citation marker rewritten to display_index
    assert "[^1]" in html
    assert "[^eodhd_1]" not in html

    # Chart embedded as data URL
    assert "src=\"data:image/png;base64," in html

    # Bibliography section present with EODHD entry
    assert 'class="v3-bibliography"' in html
    assert "EODHD" in html

    # rendered_url persisted on the Chart row
    _, _, charts, _ = svc.get_run(
        db=db_session, user_id=user.id, report_id=outcome.report_id
    )
    growth_row = next(c for c in charts if c.chart_id == "growth")
    assert growth_row.rendered_url is not None
    assert growth_row.rendered_url.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_render_html_unknown_report_raises_not_found(
    create_tables, db_session: Session
):
    user = _make_user(db_session)
    with pytest.raises(svc.ReportNotFoundError):
        render_svc.render_html(
            db=db_session, user_id=user.id, report_id=str(uuid.uuid4())
        )
