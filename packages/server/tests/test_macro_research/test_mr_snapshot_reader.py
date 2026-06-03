"""MrDashboardSnapshotReader — reads the latest cached dashboard payload from
MrDashboardCache and derives its cross-department snapshot value."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import openlia_server.db.models.register_all  # noqa: F401 — register all tables
import pytest
from openlia.macro_research.schemas import SnapshotEntry
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardCache
from openlia_server.services.mr_snapshot_reader import MrDashboardSnapshotReader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _debt_cycle_payload(phase_title: str = "Late Plateau") -> dict:
    return {
        "header": {"title": "T1", "subtitle": "s", "pills": []},
        "cardSummary": "x",
        "scorecard": {"rows": []},
        "phaseBox": {"title": phase_title, "body": "b", "tone": "amber"},
        "analogPair": {
            "analog": {"title": "a", "body": "b"},
            "timeToConstraint": {"title": "t", "body": "b"},
        },
        "policySpace": {"cards": []},
        "assetThesis": {
            "gold": {"title": "g", "body": "b"},
            "longBond": {"title": "l", "body": "b"},
        },
        "watchlist": {"rows": []},
        "verdict": {"title": "v", "body": "b", "tone": "amber"},
        "sources": "s",
        "generated_at": "2026-06-03T00:00:00Z",
    }


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as s:
        s.add(User(id="u-1", email="a@b", password_hash="x", display_name="A"))
        s.commit()
    return SessionLocal


def test_reader_returns_entry_for_seeded_debt_cycle(session_factory) -> None:
    with session_factory() as s:
        s.add(
            MrDashboardCache(
                user_id="u-1",
                dashboard="debt_cycle",
                payload_json=json.dumps(_debt_cycle_payload("Late Plateau")),
                provenance="live",
                model_ref="anthropic:claude",
                generated_at=datetime.now(UTC),
            )
        )
        s.commit()

    reader = MrDashboardSnapshotReader(session_factory=session_factory)
    entry = reader.latest_snapshot(user_id="u-1", dashboard="debt_cycle")

    assert isinstance(entry, SnapshotEntry)
    assert entry.value == "Late Plateau"
    assert entry.generated_at.tzinfo is not None


def test_reader_returns_none_for_missing_row(session_factory) -> None:
    reader = MrDashboardSnapshotReader(session_factory=session_factory)
    assert reader.latest_snapshot(user_id="u-1", dashboard="debt_cycle") is None


def test_reader_returns_none_for_non_snapshot_dashboard(session_factory) -> None:
    with session_factory() as s:
        s.add(
            MrDashboardCache(
                user_id="u-1",
                dashboard="summary",
                payload_json=json.dumps({"anything": True}),
                provenance="live",
                model_ref="anthropic:claude",
                generated_at=datetime.now(UTC),
            )
        )
        s.commit()

    reader = MrDashboardSnapshotReader(session_factory=session_factory)
    assert reader.latest_snapshot(user_id="u-1", dashboard="summary") is None


def test_reader_returns_none_for_undervable_payload(session_factory) -> None:
    with session_factory() as s:
        s.add(
            MrDashboardCache(
                user_id="u-1",
                dashboard="debt_cycle",
                payload_json=json.dumps({"junk": True}),
                provenance="live",
                model_ref="anthropic:claude",
                generated_at=datetime.now(UTC),
            )
        )
        s.commit()

    reader = MrDashboardSnapshotReader(session_factory=session_factory)
    assert reader.latest_snapshot(user_id="u-1", dashboard="debt_cycle") is None
