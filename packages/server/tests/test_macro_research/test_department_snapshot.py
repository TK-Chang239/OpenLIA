"""MRSnapshot integration test — exercises MacroResearchDepartment against
an in-memory SnapshotReader mirroring what MrDashboardSnapshotReader provides
in production. The reader returns already-derived SnapshotEntry values; the
department only assembles them and computes the 24h staleness flag."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia.departments.macro_research import MacroResearchDepartment
from openlia.macro_research.schemas import SnapshotEntry


class _FakeReader:
    def __init__(self, entries: dict[str, SnapshotEntry] | None = None) -> None:
        self._entries = entries or {}

    def latest_snapshot(self, *, user_id: str, dashboard: str) -> SnapshotEntry | None:
        return self._entries.get(dashboard)


def test_snapshot_empty_reader_returns_blank_snapshot() -> None:
    dept = MacroResearchDepartment(snapshot_reader=None)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.debt_cycle_phase is None
    assert snap.economic_season is None
    assert snap.active_force_count is None
    assert snap.generated_at is None
    assert snap.is_stale is False


def test_snapshot_fresh_entries_populate_fields() -> None:
    now = datetime.now(UTC)
    reader = _FakeReader(
        {
            "debt_cycle": SnapshotEntry(value="Late Plateau", generated_at=now),
            "four_seasons": SnapshotEntry(value="Summer", generated_at=now),
            "five_forces": SnapshotEntry(value=3, generated_at=now),
        }
    )
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.debt_cycle_phase == "Late Plateau"
    assert snap.economic_season == "Summer"
    assert snap.active_force_count == 3
    assert snap.generated_at == now
    assert snap.is_stale is False


def test_snapshot_generated_at_is_min_across_entries() -> None:
    now = datetime.now(UTC)
    older = now - timedelta(hours=2)
    oldest = now - timedelta(hours=5)
    reader = _FakeReader(
        {
            "debt_cycle": SnapshotEntry(value="Plateau", generated_at=now),
            "four_seasons": SnapshotEntry(value="Spring", generated_at=older),
            "five_forces": SnapshotEntry(value=2, generated_at=oldest),
        }
    )
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.generated_at == oldest


def test_snapshot_marks_stale_when_any_entry_older_than_24h() -> None:
    now = datetime.now(UTC)
    stale = now - timedelta(hours=30)
    reader = _FakeReader(
        {
            "debt_cycle": SnapshotEntry(value="Plateau", generated_at=stale),
            "four_seasons": SnapshotEntry(value="Spring", generated_at=now),
        }
    )
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.is_stale is True


def test_snapshot_partial_only_five_forces() -> None:
    now = datetime.now(UTC)
    reader = _FakeReader({"five_forces": SnapshotEntry(value=4, generated_at=now)})
    dept = MacroResearchDepartment(snapshot_reader=reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.debt_cycle_phase is None
    assert snap.economic_season is None
    assert snap.active_force_count == 4
    assert snap.generated_at == now
    assert snap.is_stale is False


def test_set_snapshot_reader_injects_after_construction() -> None:
    now = datetime.now(UTC)
    dept = MacroResearchDepartment()
    assert dept.get_current_snapshot(user_id="u1").debt_cycle_phase is None

    reader = _FakeReader({"debt_cycle": SnapshotEntry(value="Bottom", generated_at=now)})
    dept.set_snapshot_reader(reader)
    snap = dept.get_current_snapshot(user_id="u1")

    assert snap.debt_cycle_phase == "Bottom"
