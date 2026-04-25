from __future__ import annotations

from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import PortfolioHolding
from openlia_server.db.models.departments import MbUserConfig
from openlia_server.services.mb_request_builder import MbRequestBuilderImpl
from sqlalchemy.orm import Session


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(
        id=user_id,
        email=f"{user_id}@x",
        display_name=user_id,
        password_hash="x",
        is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


def test_build_uses_defaults_when_no_config(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    builder = MbRequestBuilderImpl()
    req: ReportRequest = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.mode == "morning_briefing"
    assert len(req.enabled_sections) == 7
    assert req.length == "standard"
    assert req.custom_sections == []


def test_build_maps_length_vocab(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="concise",
            enabled_section_ids=["executive_summary"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    )
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.length == "brief"


def test_build_passes_enabled_sections_and_customs(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="elaborative",
            enabled_section_ids=["executive_summary", "global_macro"],
            section_topics={"global_macro": [{"topic": "War", "notes": "Ukraine"}]},
            custom_sections=[{"id": "abc", "title": "My Focus", "description": "FX desk view"}],
            reference_portfolio=False,
        )
    )
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.enabled_sections == ["executive_summary", "global_macro"]
    assert req.length == "long"
    assert any(cs["title"] == "My Focus" for cs in req.custom_sections)
    assert req.section_topics == {"global_macro": [{"topic": "War", "notes": "Ukraine"}]}
    assert "MB_EXTRAS_JSON" not in req.user_input


def test_build_injects_reference_portfolio_when_enabled(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=["upcoming_preview"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=True,
        )
    )
    db_session.add(PortfolioHolding(id="h1", user_id="u_1", ticker="AAPL", name="Apple Inc."))
    db_session.add(PortfolioHolding(id="h2", user_id="u_1", ticker="NVDA", name="NVIDIA"))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.reference_portfolio is not None
    tickers = [h["ticker"] for h in req.reference_portfolio]
    assert "AAPL" in tickers
    assert "NVDA" in tickers
    assert "MB_EXTRAS_JSON" not in req.user_input


def test_build_skips_reference_portfolio_when_toggle_off(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=["upcoming_preview"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    )
    db_session.add(PortfolioHolding(id="h1", user_id="u_1", ticker="AAPL", name="Apple Inc."))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.reference_portfolio is None
    assert "AAPL" not in req.user_input


def test_build_reference_portfolio_gracefully_absent(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=["upcoming_preview"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=True,
        )
    )
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.mode == "morning_briefing"


def test_build_user_scoped_portfolio(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=["upcoming_preview"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=True,
        )
    )
    db_session.add(PortfolioHolding(id="h1", user_id="u_2", ticker="TSLA", name="Tesla"))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.reference_portfolio is None
    assert "TSLA" not in req.user_input
