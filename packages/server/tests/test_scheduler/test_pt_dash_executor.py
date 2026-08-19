"""Tests for PtDashExecutor — the PT warm-cache fan-out job (audit F2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import PtDashboardCache, PtUserConfig
from openlia_server.scheduler.executors.pt_dash import PtDashExecutor
from sqlalchemy.orm import Session


def _seed_user(session: Session, uid: str, *, disabled: bool = False) -> None:
    session.add(
        User(
            id=uid,
            email=f"{uid}@e.com",
            display_name=uid,
            password_hash="h",
            is_admin=False,
            is_disabled=disabled,
        )
    )
    session.add(
        PtUserConfig(
            id=f"cfg_{uid}",
            user_id=uid,
            panel_config=[],
            composite_settings={},
        )
    )


@dataclass
class _FakePayload:
    panels: dict = field(default_factory=dict)
    composite: dict = field(default_factory=lambda: {"level": "calm", "score": 0.0})
    generated_at: str = "2026-08-18T12:00:00+00:00"
    warnings: list = field(default_factory=list)


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def compute_dashboard(self, user_id: str) -> _FakePayload:
        self.calls.append(user_id)
        return _FakePayload(panels={"oil": {"status": "green"}})


@pytest.mark.asyncio
async def test_pt_dash_fans_out_over_enabled_pt_users(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s, "u_active")
        _seed_user(s, "u_disabled", disabled=True)
        s.add(
            User(
                id="u_never_used_pt",
                email="n@e.com",
                display_name="n",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.commit()

    runner = _FakeRunner()
    ex = PtDashExecutor(session_factory=session_factory, runner_provider=lambda: runner)
    outcome = await ex._do_work(user_id=None, schedule_id=None, run_id="r1", cancel_token=None)

    assert runner.calls == ["u_active"]
    assert outcome.result_summary == {"users": 1, "computed": 1, "failed": 0}
    with session_factory() as s:
        rows = s.query(PtDashboardCache).all()
        assert [r.user_id for r in rows] == ["u_active"]
        assert json.loads(rows[0].payload_json)["panels"] == {"oil": {"status": "green"}}


@pytest.mark.asyncio
async def test_pt_dash_counts_per_user_failures(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s, "u_ok")
        _seed_user(s, "u_boom")
        s.commit()

    class _Flaky(_FakeRunner):
        def compute_dashboard(self, user_id: str) -> _FakePayload:
            if user_id == "u_boom":
                raise RuntimeError("upstream down")
            return super().compute_dashboard(user_id)

    runner = _Flaky()
    ex = PtDashExecutor(session_factory=session_factory, runner_provider=lambda: runner)
    outcome = await ex._do_work(user_id=None, schedule_id=None, run_id="r1", cancel_token=None)

    assert outcome.result_summary["computed"] == 1
    assert outcome.result_summary["failed"] == 1


@pytest.mark.asyncio
async def test_pt_dash_skips_cleanly_without_runner(session_factory) -> None:
    ex = PtDashExecutor(session_factory=session_factory, runner_provider=lambda: None)
    outcome = await ex._do_work(user_id=None, schedule_id=None, run_id="r1", cancel_token=None)
    assert outcome.result_summary == {"skipped": "pt runner not wired"}
