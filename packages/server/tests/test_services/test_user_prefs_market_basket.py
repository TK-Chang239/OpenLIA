"""Tests for the default_market_basket user preference (fix-chats).

Snapshot basket per Q5/Q6/Q10: four editable sections (tape / risk / macro
/ crypto). Top-movers sector ETFs stay hardcoded — not user-editable.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.services import user_prefs as svc


@pytest.fixture
def user(create_tables, db_session: Session) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="basket@test.com",
        password_hash="x",
        display_name="Basket Tester",
    )
    db_session.add(u)
    db_session.flush()
    return u


def test_default_market_basket_constant_shape() -> None:
    """DEFAULT_MARKET_BASKET must match the locked Basket B from Q5."""
    assert svc.DEFAULT_MARKET_BASKET == {
        "tape": ["SPY", "QQQ", "DIA", "IWM"],
        "risk": ["VIX", "HYG", "TLT"],
        "macro": ["DXY", "GLD", "USO"],
        "crypto": ["BTC"],
    }


def test_get_market_basket_returns_default_when_unset(db_session: Session, user: User) -> None:
    basket = svc.get_market_basket(db_session, user_id=user.id)
    assert basket == svc.DEFAULT_MARKET_BASKET


def test_set_market_basket_persists_full_basket(db_session: Session, user: User) -> None:
    custom = {
        "tape": ["SPY", "QQQ"],
        "risk": ["VIX"],
        "macro": ["DXY"],
        "crypto": ["BTC", "ETH"],
    }
    svc.set_market_basket(db_session, user_id=user.id, basket=custom)
    db_session.flush()
    assert svc.get_market_basket(db_session, user_id=user.id) == custom


def test_set_market_basket_rejects_missing_section(db_session: Session, user: User) -> None:
    with pytest.raises(ValueError, match="missing section"):
        svc.set_market_basket(
            db_session,
            user_id=user.id,
            basket={"tape": ["SPY"], "risk": ["VIX"], "macro": ["DXY"]},
        )


def test_set_market_basket_rejects_unknown_section(db_session: Session, user: User) -> None:
    with pytest.raises(ValueError, match="unknown section"):
        svc.set_market_basket(
            db_session,
            user_id=user.id,
            basket={
                "tape": ["SPY"],
                "risk": ["VIX"],
                "macro": ["DXY"],
                "crypto": ["BTC"],
                "extra": ["XXX"],
            },
        )


def test_set_market_basket_rejects_too_many_tickers(db_session: Session, user: User) -> None:
    """Cap is 12 tickers per section."""
    with pytest.raises(ValueError, match="too many tickers"):
        svc.set_market_basket(
            db_session,
            user_id=user.id,
            basket={
                "tape": [f"T{i:02d}" for i in range(13)],
                "risk": ["VIX"],
                "macro": ["DXY"],
                "crypto": ["BTC"],
            },
        )


def test_set_market_basket_rejects_invalid_ticker_format(db_session: Session, user: User) -> None:
    with pytest.raises(ValueError, match="invalid ticker"):
        svc.set_market_basket(
            db_session,
            user_id=user.id,
            basket={
                "tape": ["spy lowercase"],
                "risk": ["VIX"],
                "macro": ["DXY"],
                "crypto": ["BTC"],
            },
        )


def test_set_market_basket_rejects_empty_section(db_session: Session, user: User) -> None:
    with pytest.raises(ValueError, match="empty"):
        svc.set_market_basket(
            db_session,
            user_id=user.id,
            basket={
                "tape": [],
                "risk": ["VIX"],
                "macro": ["DXY"],
                "crypto": ["BTC"],
            },
        )


def test_set_market_basket_normalizes_to_uppercase(db_session: Session, user: User) -> None:
    """Common ticker forms with valid characters in any case — normalize."""
    svc.set_market_basket(
        db_session,
        user_id=user.id,
        basket={
            "tape": ["spy", "QqQ"],
            "risk": [" vix "],
            "macro": ["dxy"],
            "crypto": ["btc"],
        },
    )
    db_session.flush()
    out = svc.get_market_basket(db_session, user_id=user.id)
    assert out["tape"] == ["SPY", "QQQ"]
    assert out["risk"] == ["VIX"]
    assert out["macro"] == ["DXY"]
    assert out["crypto"] == ["BTC"]
