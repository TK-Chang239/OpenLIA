from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from openlia_server.db.base import Base
from openlia_server.db.models.dashboard import MrAssessmentCache
from openlia_server.services.mr_cache import MRCacheStoreImpl


@pytest.fixture
def session_factory():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, expire_on_commit=False)


def test_save_inserts_row(session_factory) -> None:
    store = MRCacheStoreImpl()
    with session_factory() as s:
        cache_id = store.save(
            session=s,
            user_id="u-1",
            payload={
                "dashboard": "world_order",
                "assessment_type": "synthesis",
                "input_hash": "abc123",
                "result": {"stage": "Pressure"},
                "model_ref": "openai:gpt-4o",
                "token_usage": {"prompt": 100, "completion": 200},
                "ttl_hours": 168,
            },
        )
        s.commit()
        assert cache_id
        row = s.get(MrAssessmentCache, cache_id)
        assert row is not None
        assert row.dashboard == "world_order"
        assert row.result == {"stage": "Pressure"}


def test_read_latest_returns_most_recent(session_factory) -> None:
    store = MRCacheStoreImpl()
    now = datetime.now(UTC)
    with session_factory() as s:
        for i in range(3):
            s.add(
                MrAssessmentCache(
                    id=f"mac-{i}",
                    dashboard="world_order",
                    assessment_type="synthesis",
                    input_hash=f"h{i}",
                    result={"stage": f"S{i}"},
                    model_ref="openai:gpt-4o",
                    token_usage=None,
                    generated_at=now - timedelta(days=i),
                    expires_at=now + timedelta(days=10),
                )
            )
        s.commit()
        latest = store.read_latest(
            session=s, user_id="u-1", dashboard="world_order", assessment_type="synthesis"
        )
        assert latest is not None
        assert latest["result"] == {"stage": "S0"}


def test_read_latest_skips_expired(session_factory) -> None:
    store = MRCacheStoreImpl()
    now = datetime.now(UTC)
    with session_factory() as s:
        s.add(
            MrAssessmentCache(
                id="mac-exp",
                dashboard="world_order",
                assessment_type="synthesis",
                input_hash="h",
                result={"stage": "X"},
                model_ref="openai:gpt-4o",
                token_usage=None,
                generated_at=now - timedelta(days=200),
                expires_at=now - timedelta(days=100),
            )
        )
        s.commit()
        latest = store.read_latest(
            session=s, user_id="u-1", dashboard="world_order", assessment_type="synthesis"
        )
        assert latest is None
