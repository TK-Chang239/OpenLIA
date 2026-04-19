from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from _fakes import (
    FakeEUPlanner,
    FakeReportRunner,
    FakeReportStore,
    FakeSleep,
)
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportStart,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import (
    EuSchedule,
    JobRun,
    UserNotification,
)
from openlia_server.scheduler.executors.eu import EUScanExecutor
from openlia_server.scheduler.payloads import EUScanTarget
from openlia_server.scheduler.registry import JobStatus


def _seed(session: Session) -> None:
    session.add(
        User(
            id="u_1", email="u@e.com", display_name="u",
            password_hash="h", is_admin=False, is_disabled=False,
        )
    )
    session.add(
        EuSchedule(
            id="sch_eu", user_id="u_1",
            time="16:30", timezone="America/New_York",
            days_of_week='["mon","tue","wed","thu","fri"]',
            label="Post-Market", is_enabled=True,
            created_at=datetime.now(timezone.utc), last_run_at=None,
        )
    )
    session.commit()


def _ok_events(report_id: str, ticker: str) -> list:
    return [
        ReportStart(
            report_id=report_id, department="earnings_update",
            mode="stock_update", section_titles=["Scorecard"],
        ),
        ReportComplete(
            report_id=report_id,
            schema={"title": f"{ticker} earnings", "sections": []},
        ),
    ]


class _ScriptedMultiRunner:
    """ReportRunner fake that yields different event streams per call."""

    def __init__(self, streams: list[list]) -> None:
        self._streams = list(streams)
        self.calls: list[dict] = []

    async def run(self, *, department_id, user_id, request, cancel_token=None):
        self.calls.append(
            {"department_id": department_id, "user_id": user_id, "request": request}
        )
        stream = self._streams.pop(0)
        for ev in stream:
            yield ev


@pytest.mark.asyncio
async def test_eu_scan_no_new_earnings_completes_with_zero_reports(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    planner = FakeEUPlanner(targets=[])
    runner = _ScriptedMultiRunner(streams=[])
    store = FakeReportStore()

    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        eu_planner=planner,
        report_runner=runner,
        report_store=store,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_eu")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        summary = json.loads(row.result_summary)
        assert summary == {"reports_generated": 0, "report_ids": []}
        assert s.query(UserNotification).count() == 0
        assert s.get(EuSchedule, "sch_eu").last_run_at is not None


@pytest.mark.asyncio
async def test_eu_scan_runs_each_target_sequentially_and_notifies_each(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    targets = [
        EUScanTarget(
            ticker="AAPL",
            request=ReportRequest(mode="stock_update", user_input="AAPL"),
        ),
        EUScanTarget(
            ticker="MSFT",
            request=ReportRequest(mode="stock_update", user_input="MSFT"),
        ),
        EUScanTarget(
            ticker="NVDA",
            request=ReportRequest(mode="stock_update", user_input="NVDA"),
        ),
    ]
    runner = _ScriptedMultiRunner(
        streams=[
            _ok_events("r_aapl", "AAPL"),
            _ok_events("r_msft", "MSFT"),
            _ok_events("r_nvda", "NVDA"),
        ]
    )
    store = FakeReportStore()
    # Return distinct IDs per save.
    saved_ids: list[str] = []

    def _save(*, session, user_id, department, payload):
        saved_ids.append(f"rep_{len(saved_ids)+1}")
        store.saves.append(
            {
                "user_id": user_id,
                "department": department,
                "payload": payload,
            }
        )
        return saved_ids[-1]

    store.save = _save  # type: ignore[method-assign]

    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        eu_planner=FakeEUPlanner(targets=targets),
        report_runner=runner,
        report_store=store,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_eu")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        summary = json.loads(row.result_summary)
        assert summary == {
            "reports_generated": 3,
            "report_ids": ["rep_1", "rep_2", "rep_3"],
        }

        notifs = sorted(
            s.query(UserNotification).all(), key=lambda n: n.message
        )
        assert len(notifs) == 3
        messages = [n.message for n in notifs]
        assert "AAPL" in messages[0]
        assert "MSFT" in messages[1]
        assert "NVDA" in messages[2]
        for n in notifs:
            assert n.type == "report_ready"
            assert n.department == "earnings_update"

    # The runner must be called once per target, in order.
    tickers_called = [c["request"].user_input for c in runner.calls]
    assert tickers_called == ["AAPL", "MSFT", "NVDA"]


@pytest.mark.asyncio
async def test_eu_planner_receives_last_run_at_as_since(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)
        previous = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
        s.get(EuSchedule, "sch_eu").last_run_at = previous
        s.commit()

    planner = FakeEUPlanner(targets=[])
    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        eu_planner=planner,
        report_runner=_ScriptedMultiRunner(streams=[]),
        report_store=FakeReportStore(),
    )
    await ex.execute(user_id="u_1", schedule_id="sch_eu")
    assert planner.received[0]["since"] is not None
    assert planner.received[0]["since"].hour == 12


@pytest.mark.asyncio
async def test_eu_mid_scan_transient_error_triggers_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    targets = [
        EUScanTarget(
            ticker="AAPL",
            request=ReportRequest(mode="stock_update", user_input="AAPL"),
        ),
        EUScanTarget(
            ticker="MSFT",
            request=ReportRequest(mode="stock_update", user_input="MSFT"),
        ),
    ]

    # First attempt: AAPL succeeds, MSFT hits a RateLimitError.
    # Second attempt: both succeed.
    first_attempt = [
        _ok_events("r_aapl_1", "AAPL"),
        [
            ReportStart(
                report_id="r_msft_1", department="earnings_update",
                mode="stock_update", section_titles=[],
            ),
            ReportError(
                report_id="r_msft_1",
                error_class="RateLimitError",
                message="429",
            ),
        ],
    ]
    second_attempt = [
        _ok_events("r_aapl_2", "AAPL"),
        _ok_events("r_msft_2", "MSFT"),
    ]
    runner = _ScriptedMultiRunner(streams=first_attempt + second_attempt)
    sleep = FakeSleep()

    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=sleep,
        eu_planner=FakeEUPlanner(targets=targets),
        report_runner=runner,
        report_store=FakeReportStore(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_eu")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 2
    assert sleep.calls == [30]
