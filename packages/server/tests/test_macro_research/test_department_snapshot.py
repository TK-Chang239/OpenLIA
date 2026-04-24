"""MRSnapshot integration test — exercises MacroResearchDepartment against
an in-memory SnapshotReader mirroring what MRDashboardService/MRAssessmentCache
provide in production. Verifies stale flag behavior across 24h live-tier
windows and schedule-aware T5 synthesis windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from openlia.departments.macro_research import MacroResearchDepartment


class _FakeReader:
    def __init__(
        self,
        *,
        states: dict[str, dict[str, Any]] | None = None,
        assessments: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self._states = states or {}
        self._assessments = assessments or {}

    def latest_state(self, *, user_id: str, dashboard: str) -> dict[str, Any] | None:
        return self._states.get(dashboard)

    def latest_assessment(
        self, *, user_id: str, dashboard: str, assessment_type: str
    ) -> dict[str, Any] | None:
        return self._assessments.get((dashboard, assessment_type))


def test_snapshot_empty_reader_returns_blank_snapshot() -> None:
    dept = MacroResearchDepartment(snapshot_reader=None)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.debt_cycle_phase is None
    assert snap.economic_season is None
    assert snap.active_force_count is None
    assert snap.generated_at is None
    assert snap.is_stale is False


def test_snapshot_fresh_reads_are_not_stale() -> None:
    now = datetime.now(UTC)
    reader = _FakeReader(
        states={
            "debt_cycle": {"phase": "Late Plateau", "generated_at": now},
            "four_seasons": {"season": "Summer", "generated_at": now},
        },
        assessments={
            ("five_forces", "synthesis"): {
                "active_force_count": 3,
                "schedule": "quarterly",
                "generated_at": now,
            },
        },
    )
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.debt_cycle_phase == "Late Plateau"
    assert snap.economic_season == "Summer"
    assert snap.active_force_count == 3
    assert snap.generated_at is not None
    assert snap.is_stale is False


def test_snapshot_marks_stale_when_live_tier_older_than_24h() -> None:
    now = datetime.now(UTC)
    old = now - timedelta(hours=30)
    reader = _FakeReader(
        states={
            "debt_cycle": {"phase": "Plateau", "generated_at": old},
            "four_seasons": {"season": "Spring", "generated_at": now},
        },
    )
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.is_stale is True


def test_snapshot_marks_stale_when_quarterly_t5_older_than_95_days() -> None:
    now = datetime.now(UTC)
    very_old = now - timedelta(days=120)
    reader = _FakeReader(
        assessments={
            ("five_forces", "synthesis"): {
                "active_force_count": 2,
                "schedule": "quarterly",
                "generated_at": very_old,
            },
        },
    )
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.is_stale is True
    assert snap.active_force_count == 2


def test_snapshot_weekly_t5_window_is_8_days() -> None:
    now = datetime.now(UTC)
    within = now - timedelta(days=7)
    reader = _FakeReader(
        assessments={
            ("five_forces", "synthesis"): {
                "active_force_count": 1,
                "schedule": "weekly",
                "generated_at": within,
            },
        },
    )
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")
    assert snap.is_stale is False

    reader_stale = _FakeReader(
        assessments={
            ("five_forces", "synthesis"): {
                "active_force_count": 1,
                "schedule": "weekly",
                "generated_at": now - timedelta(days=9),
            },
        },
    )
    assert (
        MacroResearchDepartment(snapshot_reader=reader_stale)
        .get_current_snapshot(user_id="u1")
        .is_stale
        is True
    )
