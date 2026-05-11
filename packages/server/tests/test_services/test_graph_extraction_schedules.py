"""Slice 6 (runtime spec) — per-user graph-extraction schedule wiring tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from apscheduler.triggers.cron import CronTrigger
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.config import UserPrefs
from openlia_server.scheduler.registry import JobType, job_key
from openlia_server.services.graph_extraction_schedules import (
    ensure_schedule_registered,
    remove_schedule,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def session_factory():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, future=True, expire_on_commit=False)


@dataclass
class _FakeAPS:
    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    raise_on_remove_missing: bool = False
    _ids: set[str] = field(default_factory=set)

    async def add_schedule(self, func, trigger, *, id, args, **kwargs):
        self.added.append({"id": id, "trigger": trigger, "args": args, "kwargs": kwargs})
        self._ids.add(id)
        return id

    async def remove_schedule(self, id):
        if id not in self._ids:
            if self.raise_on_remove_missing:
                raise KeyError(id)
            return
        self._ids.discard(id)
        self.removed.append(id)


def _callback(*_args, **_kwargs):
    pass


def _seed(session, *, user_id: str, time: str = "03:00", tz: str = "UTC"):
    session.add(
        User(
            id=user_id,
            email=f"{user_id}@e.com",
            display_name=user_id,
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.add(
        UserPrefs(
            user_id=user_id,
            theme="system",
            notify_inapp=True,
            notify_email=False,
            display_language="en",
            response_language="en",
            report_language="en",
            timezone=tz,
            timezone_source="manual",
            graph_extraction_time=time,
        )
    )
    session.commit()


@pytest.mark.asyncio
async def test_ensure_registers_cron_trigger_with_user_timezone(session_factory) -> None:
    with session_factory() as s:
        _seed(s, user_id="u_1", time="07:30", tz="America/New_York")

    sched = _FakeAPS()
    with session_factory() as s:
        jid = await ensure_schedule_registered(
            db=s,
            user_id="u_1",
            scheduler_control=sched,
            callback=_callback,
        )

    assert jid == job_key(JobType.GRAPH_EXTRACTION, "u_1")
    assert len(sched.added) == 1
    entry = sched.added[0]
    assert entry["id"] == jid
    trigger = entry["trigger"]
    assert isinstance(trigger, CronTrigger)
    # CronTrigger fields_map uses field names — verify hour + minute.
    assert str(trigger).find("hour='7'") != -1 or "hour=7" in str(trigger)
    assert "minute='30'" in str(trigger) or "minute=30" in str(trigger)
    assert "America/New_York" in str(trigger)
    # Args are (job_type, user_id, schedule_id=None)
    assert entry["args"] == (JobType.GRAPH_EXTRACTION, "u_1", None)


@pytest.mark.asyncio
async def test_ensure_is_idempotent_removes_then_adds(session_factory) -> None:
    with session_factory() as s:
        _seed(s, user_id="u_1")

    sched = _FakeAPS()
    with session_factory() as s:
        await ensure_schedule_registered(
            db=s, user_id="u_1", scheduler_control=sched, callback=_callback
        )
    # Second call: should re-register without raising.
    with session_factory() as s:
        await ensure_schedule_registered(
            db=s, user_id="u_1", scheduler_control=sched, callback=_callback
        )

    # Two adds total, one remove (between the two adds).
    assert len(sched.added) == 2
    assert len(sched.removed) == 1


@pytest.mark.asyncio
async def test_ensure_swallows_remove_error_on_first_register(session_factory) -> None:
    """When no prior registration exists, the remove call's exception
    must not abort the add."""
    with session_factory() as s:
        _seed(s, user_id="u_1")

    sched = _FakeAPS(raise_on_remove_missing=True)
    with session_factory() as s:
        jid = await ensure_schedule_registered(
            db=s, user_id="u_1", scheduler_control=sched, callback=_callback
        )
    assert jid == job_key(JobType.GRAPH_EXTRACTION, "u_1")
    assert len(sched.added) == 1


@pytest.mark.asyncio
async def test_ensure_raises_when_user_has_no_prefs(session_factory) -> None:
    # User exists but no UserPrefs row.
    with session_factory() as s:
        s.add(
            User(
                id="u_2",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.commit()

    sched = _FakeAPS()
    with session_factory() as s:
        with pytest.raises(ValueError, match="no user_prefs"):
            await ensure_schedule_registered(
                db=s, user_id="u_2", scheduler_control=sched, callback=_callback
            )
    assert sched.added == []


@pytest.mark.asyncio
async def test_remove_schedule_calls_aps_remove() -> None:
    sched = _FakeAPS()
    sched._ids.add(job_key(JobType.GRAPH_EXTRACTION, "u_1"))
    await remove_schedule(user_id="u_1", scheduler_control=sched)
    assert sched.removed == [job_key(JobType.GRAPH_EXTRACTION, "u_1")]


@pytest.mark.asyncio
async def test_remove_schedule_swallows_missing_id() -> None:
    sched = _FakeAPS(raise_on_remove_missing=True)
    # Should not raise even though no entry exists.
    await remove_schedule(user_id="u_unknown", scheduler_control=sched)
