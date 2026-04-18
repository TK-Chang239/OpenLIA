from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.auth
    import openlia_server.db.models.config
    import openlia_server.db.models.content  # noqa: F401
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_chat_message_cascade_from_session(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import ChatMessage, ChatSession

    u = User(id="u1", email="u1@example.com", display_name="U1")
    cs = ChatSession(id="cs1", user_id="u1", department="secretary")
    msg = ChatMessage(id="m1", session_id="cs1", role="user", content="hi")
    db_session.add_all([u, cs, msg])
    db_session.commit()

    db_session.delete(cs)
    db_session.commit()
    assert db_session.execute(select(ChatMessage)).scalar_one_or_none() is None


def test_report_user_id_set_null_on_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import Report

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1",
        user_id="u1",
        department="equity_research",
        report_type="stock_update",
        title="AAPL Update",
        content_markdown="# AAPL",
        content_structured={},
        model_ref="gpt-4o",
    )
    db_session.add_all([u, r])
    db_session.commit()

    db_session.delete(u)
    db_session.commit()

    row = db_session.execute(select(Report)).scalar_one()
    assert row.user_id is None


def test_report_version_unique_per_report(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import Report, ReportVersion

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1",
        user_id="u1",
        department="equity_research",
        report_type="stock_update",
        title="t",
        content_markdown="m",
        content_structured={},
        model_ref="m",
    )
    v1 = ReportVersion(
        id="v1", report_id="r1", version_number=1, content_markdown="m", content_structured={}
    )
    v2 = ReportVersion(
        id="v2", report_id="r1", version_number=1, content_markdown="m", content_structured={}
    )
    db_session.add_all([u, r, v1, v2])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_portfolio_unique_user_ticker(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import PortfolioHolding

    u = User(id="u1", email="u1@example.com", display_name="U1")
    h1 = PortfolioHolding(id="h1", user_id="u1", ticker="AAPL")
    h2 = PortfolioHolding(id="h2", user_id="u1", ticker="AAPL")
    db_session.add_all([u, h1, h2])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watchlist_item_composite_pk(create_tables) -> None:
    from openlia_server.db.models.content import WatchlistItem

    pk_cols = {c.name for c in WatchlistItem.__table__.primary_key}
    assert pk_cols == {"watchlist_id", "ticker"}


def test_chat_session_indexes(create_tables) -> None:
    from openlia_server.db.models.content import ChatSession

    idx_names = {i.name for i in ChatSession.__table__.indexes}
    assert "ix_chat_sessions_user_id_department" in idx_names
    assert "ix_chat_sessions_user_id_updated_at" in idx_names


def test_numeric_columns_use_decimal(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import PortfolioHolding

    u = User(id="u1", email="u1@example.com", display_name="U1")
    h = PortfolioHolding(
        id="h1",
        user_id="u1",
        ticker="AAPL",
        shares=Decimal("100.5"),
        cost_basis=Decimal("150.25"),
    )
    db_session.add_all([u, h])
    db_session.commit()
    db_session.refresh(h)
    assert h.shares == Decimal("100.5")


def test_tags_default_empty_list(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import Report

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1",
        user_id="u1",
        department="equity_research",
        report_type="stock_update",
        title="t",
        content_markdown="m",
        content_structured={},
        model_ref="m",
    )
    db_session.add_all([u, r])
    db_session.commit()
    db_session.refresh(r)
    assert r.tags == []
