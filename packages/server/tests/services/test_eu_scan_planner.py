from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import EuUserConfig, EuWatchlistEntry
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl
from sqlalchemy.orm import Session


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(
        id=user_id, email=f"{user_id}@x", display_name=user_id,
        password_hash="x", is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


def _add_watchlist(db: Session, user_id: str, ticker: str, company: str) -> None:
    from uuid import uuid4
    db.add(EuWatchlistEntry(
        id=f"eu_{uuid4().hex[:12]}", user_id=user_id, ticker=ticker,
        company_name=company, next_earnings_date=None, release_timing=None,
    ))
    db.commit()


@dataclass
class FakeEarningsAdapter:
    """Returns an 'earnings_released_since' lookup per ticker."""
    by_ticker: dict[str, datetime | None] = field(default_factory=dict)
    calls: list[tuple[str, datetime | None]] = field(default_factory=list)

    def latest_release(self, ticker: str, *, since: datetime | None) -> datetime | None:
        self.calls.append((ticker, since))
        return self.by_ticker.get(ticker)


def test_plan_returns_empty_if_watchlist_empty(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    planner = EuScanPlannerImpl(adapter=FakeEarningsAdapter())
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=None)
    assert targets == []


def test_plan_returns_targets_only_for_new_earnings(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _add_watchlist(db_session, "u_1", "AAPL", "Apple")
    _add_watchlist(db_session, "u_1", "TSLA", "Tesla")
    _add_watchlist(db_session, "u_1", "NVDA", "NVIDIA")

    now = datetime.now(tz=UTC)
    since = now - timedelta(hours=12)
    adapter = FakeEarningsAdapter(by_ticker={
        "AAPL": now - timedelta(hours=1),  # after since -> include
        "TSLA": now - timedelta(days=7),   # before since -> skip
        "NVDA": None,                      # no recent release -> skip
    })
    planner = EuScanPlannerImpl(adapter=adapter)
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=since)
    assert [t.ticker for t in targets] == ["AAPL"]


def test_plan_passes_since_to_adapter(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _add_watchlist(db_session, "u_1", "AAPL", "Apple")
    since = datetime(2026, 4, 1, tzinfo=UTC)
    adapter = FakeEarningsAdapter()
    planner = EuScanPlannerImpl(adapter=adapter)
    planner.plan(session=db_session, user_id="u_1", schedule_id="s_1", since=since)
    assert adapter.calls == [("AAPL", since)]


def test_plan_builds_report_request_with_ticker_and_config(
    create_tables, db_session: Session,
) -> None:
    _mk_user(db_session)
    _add_watchlist(db_session, "u_1", "AAPL", "Apple Inc.")
    now = datetime.now(tz=UTC)

    # User config: concise length, only 2 sections enabled
    db_session.add(EuUserConfig(
        id="euc_1", user_id="u_1", report_length="concise",
        enabled_section_ids=["quick_take", "key_financials"],
        custom_sections=[{
            "id": "custom_extra_1",
            "title": "Model update",
            "description": "Update base case",
        }],
    ))
    db_session.commit()

    adapter = FakeEarningsAdapter(by_ticker={"AAPL": now})
    planner = EuScanPlannerImpl(adapter=adapter)
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=now - timedelta(hours=6))
    assert len(targets) == 1
    req: ReportRequest = targets[0].request
    assert req.mode == "earnings_analysis"
    assert "AAPL" in req.user_input
    assert req.enabled_sections == ["quick_take", "key_financials"]
    assert req.custom_sections == [
        {"id": "custom_extra_1", "title": "Model update", "description": "Update base case"}
    ]
    # Config column holds "concise"; planner maps to ReportRequest.length "brief".
    assert req.length == "brief"


def test_plan_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    _add_watchlist(db_session, "u_1", "AAPL", "Apple")
    _add_watchlist(db_session, "u_2", "TSLA", "Tesla")

    now = datetime.now(tz=UTC)
    adapter = FakeEarningsAdapter(by_ticker={"AAPL": now, "TSLA": now})
    planner = EuScanPlannerImpl(adapter=adapter)
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=now - timedelta(hours=6))
    assert [t.ticker for t in targets] == ["AAPL"]
