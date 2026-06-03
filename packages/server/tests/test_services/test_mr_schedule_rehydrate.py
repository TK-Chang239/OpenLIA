"""P2-20 — Confirm an MR schedule persisted from a prior session is
re-registered with APScheduler at lifespan startup."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.scheduler.registry import JobType, job_key

# Path to the scheduler test-fakes module.
sys.path.insert(0, str(Path(__file__).parents[1] / "test_scheduler"))


class _RecordingAPScheduler:
    """Minimal AsyncScheduler shim that records `add_schedule` ids.

    Behaves enough like APScheduler 4.x to satisfy `_SchedulerAdapter`
    + SchedulerService so we can run the production lifespan path
    against it. We only need add_schedule to record ids; the live
    callbacks never fire in this test.
    """

    def __init__(self) -> None:
        self.added_schedule_ids: list[str] = []
        self.removed_schedule_ids: list[str] = []
        self.started = False
        self.stopped = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def start_in_background(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def add_schedule(self, *args, id: str, **kwargs):
        self.added_schedule_ids.append(id)
        return id

    async def remove_schedule(self, id: str) -> None:
        self.removed_schedule_ids.append(id)

    async def get_schedules(self) -> list:
        return []


def test_rehydrate_registers_persisted_mr_schedule_at_lifespan() -> None:
    db_path = Path("/tmp/openlia_mr_rehydrate_test.db")
    if db_path.exists():
        db_path.unlink()
    db_url = f"sqlite:///{db_path}"

    # Seed: create a user + an MR dashboard row with assessment_schedule.
    from openlia_server.db.base import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine(db_url, future=True)
    Base.metadata.create_all(eng)
    SessionLocal = sessionmaker(bind=eng, future=True, expire_on_commit=False)
    user_id = "u_seed"
    with SessionLocal() as s:
        s.add(
            User(
                id=user_id,
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.add(
            MrDashboardState(
                id=str(uuid.uuid4()),
                user_id=user_id,
                # Canonical MR schedule row is debt_cycle (the implemented
                # dashboard); rehydrate_all only matches the canonical slug.
                dashboard="debt_cycle",
                view_config={},
                threshold_overrides={},
                assessment_schedule="0 0 * * 0",
            )
        )
        s.commit()
    eng.dispose()

    recorder = _RecordingAPScheduler()

    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "1",
            "OPENLIA_DB_URL": db_url,
        },
        clear=False,
    ):
        # Replace the production AsyncScheduler with our recording shim.
        from openlia_server import app as app_mod
        from openlia_server.app import create_app

        with patch.object(
            app_mod._SchedulerAdapter,
            "__init__",
            lambda self, *a, **kw: (
                setattr(self, "_sched", recorder) or setattr(self, "_bg_task", None)
            ),
        ):
            app = create_app()
            with TestClient(app) as client:
                assert client.get("/health").status_code == 200
                # Rehydration writes the MR job key to the recording scheduler.
                expected = job_key(JobType.MR_DASH, user_id)
                assert expected in recorder.added_schedule_ids

    if db_path.exists():
        db_path.unlink()
