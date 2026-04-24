from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.services.mr_schedules import MRScheduleService


@pytest.fixture
def factory():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    SessionLocal = sessionmaker(bind=eng, expire_on_commit=False)
    with SessionLocal() as s:
        s.add(User(id="u-1", email="a@b", password_hash="x", display_name="A"))
        s.commit()
    return SessionLocal


@pytest.mark.asyncio
async def test_upsert_creates_then_updates(factory) -> None:
    scheduler = MagicMock()
    scheduler.modify_schedule = AsyncMock()
    svc = MRScheduleService(session_factory=factory, scheduler=scheduler)

    row = await svc.upsert(user_id="u-1", cron_expression="0 0 * * 0")
    assert row.assessment_schedule == "0 0 * * 0"
    assert scheduler.modify_schedule.await_count == 1

    row = await svc.upsert(user_id="u-1", cron_expression="0 0 1 */3 *")
    assert row.assessment_schedule == "0 0 1 */3 *"
    assert scheduler.modify_schedule.await_count == 2


@pytest.mark.asyncio
async def test_delete_removes_scheduler_and_clears_row(factory) -> None:
    scheduler = MagicMock()
    scheduler.modify_schedule = AsyncMock()
    scheduler.remove_schedule = AsyncMock()
    svc = MRScheduleService(session_factory=factory, scheduler=scheduler)

    await svc.upsert(user_id="u-1", cron_expression="0 0 * * 0")
    await svc.delete(user_id="u-1")
    scheduler.remove_schedule.assert_awaited_once()
    row = svc.get(user_id="u-1")
    assert row.assessment_schedule is None


@pytest.mark.asyncio
async def test_rehydrate_all_registers_enabled_rows(factory) -> None:
    scheduler = MagicMock()
    scheduler.add_schedule = AsyncMock()
    scheduler.modify_schedule = AsyncMock()
    svc = MRScheduleService(session_factory=factory, scheduler=scheduler)
    await svc.upsert(user_id="u-1", cron_expression="0 0 * * 0")
    count = await svc.rehydrate_all()
    assert count == 1
    scheduler.add_schedule.assert_awaited()


@pytest.mark.asyncio
async def test_delete_noop_when_no_row(factory) -> None:
    scheduler = MagicMock()
    scheduler.remove_schedule = AsyncMock()
    svc = MRScheduleService(session_factory=factory, scheduler=scheduler)
    await svc.delete(user_id="u-1")
    scheduler.remove_schedule.assert_not_awaited()
