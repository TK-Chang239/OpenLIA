"""Slice 6 (runtime spec) — boot-time rehydrate of nightly graph-extraction
schedules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.config import UserPrefs
from openlia_server.scheduler.registry import JobType, job_key
from openlia_server.services.graph_extraction_rehydrate import rehydrate_all
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
    _ids: set[str] = field(default_factory=set)

    async def add_schedule(self, func, trigger, *, id, args, **kwargs):
        self.added.append({"id": id, "args": args})
        self._ids.add(id)

    async def remove_schedule(self, id):
        self._ids.discard(id)
        self.removed.append(id)


def _callback(*_a, **_kw):
    pass


def _seed_user_with_prefs(s, user_id: str, *, disabled: bool = False) -> None:
    s.add(
        User(
            id=user_id,
            email=f"{user_id}@e.com",
            display_name=user_id,
            password_hash="h",
            is_admin=False,
            is_disabled=disabled,
        )
    )
    s.add(
        UserPrefs(
            user_id=user_id,
            theme="system",
            notify_inapp=True,
            notify_email=False,
            display_language="en",
            response_language="en",
            report_language="en",
            timezone="UTC",
            timezone_source="auto",
            graph_extraction_time="03:00",
        )
    )


@pytest.mark.asyncio
async def test_rehydrates_each_enabled_user(session_factory) -> None:
    with session_factory() as s:
        _seed_user_with_prefs(s, "u_a")
        _seed_user_with_prefs(s, "u_b")
        s.commit()

    sched = _FakeAPS()
    count = await rehydrate_all(
        session_factory=session_factory,
        scheduler_control=sched,
        callback=_callback,
    )
    assert count == 2
    ids = {entry["id"] for entry in sched.added}
    assert job_key(JobType.GRAPH_EXTRACTION, "u_a") in ids
    assert job_key(JobType.GRAPH_EXTRACTION, "u_b") in ids


@pytest.mark.asyncio
async def test_skips_disabled_users(session_factory) -> None:
    with session_factory() as s:
        _seed_user_with_prefs(s, "u_active")
        _seed_user_with_prefs(s, "u_disabled", disabled=True)
        s.commit()

    sched = _FakeAPS()
    count = await rehydrate_all(
        session_factory=session_factory,
        scheduler_control=sched,
        callback=_callback,
    )
    assert count == 1
    ids = {entry["id"] for entry in sched.added}
    assert job_key(JobType.GRAPH_EXTRACTION, "u_active") in ids
    assert job_key(JobType.GRAPH_EXTRACTION, "u_disabled") not in ids


@pytest.mark.asyncio
async def test_idempotent_on_repeat_call(session_factory) -> None:
    with session_factory() as s:
        _seed_user_with_prefs(s, "u_a")
        s.commit()

    sched = _FakeAPS()
    await rehydrate_all(
        session_factory=session_factory, scheduler_control=sched, callback=_callback
    )
    await rehydrate_all(
        session_factory=session_factory, scheduler_control=sched, callback=_callback
    )

    # Two adds (one per rehydrate). ensure_schedule_registered always
    # attempts a remove first, so the recorder sees two removes too —
    # the production APScheduler treats remove-of-missing as a no-op.
    assert len(sched.added) == 2
    assert len(sched.removed) == 2
