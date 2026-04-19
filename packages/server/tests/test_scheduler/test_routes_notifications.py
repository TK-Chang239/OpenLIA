from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import UserNotification


# Reuse the fixture from test_routes_jobs.py
pytest_plugins = ["test_routes_jobs"]


def _seed_notif(
    session,
    *,
    id: str,
    department: str,
    user_id: str = "u_1",
    read_at=None,
) -> None:
    session.add(
        UserNotification(
            id=id,
            user_id=user_id,
            type="report_ready",
            department=department,
            message=f"notif {id}",
            created_at=datetime.now(timezone.utc),
            read_at=read_at,
        )
    )


def test_unread_returns_counts_by_department(
    client_with_user, route_session_factory
) -> None:
    with route_session_factory() as s:
        _seed_notif(s, id="n1", department="morning_briefing")
        _seed_notif(s, id="n2", department="morning_briefing")
        _seed_notif(s, id="n3", department="earnings_update")
        _seed_notif(
            s, id="n4", department="morning_briefing",
            read_at=datetime.now(timezone.utc),
        )
        s.commit()

    r = client_with_user.get("/notifications/unread")
    assert r.status_code == 200
    body = r.json()
    assert body["by_department"] == {
        "morning_briefing": 2,
        "earnings_update": 1,
    }
    assert body["total"] == 3


def test_mark_read_flips_all_department_notifications(
    client_with_user, route_session_factory
) -> None:
    with route_session_factory() as s:
        _seed_notif(s, id="n1", department="morning_briefing")
        _seed_notif(s, id="n2", department="morning_briefing")
        _seed_notif(s, id="n3", department="earnings_update")
        s.commit()

    r = client_with_user.post(
        "/notifications/read",
        json={"department": "morning_briefing"},
    )
    assert r.status_code == 200
    assert r.json() == {"marked_read": 2}

    with route_session_factory() as s:
        remaining = (
            s.query(UserNotification)
            .filter(UserNotification.read_at.is_(None))
            .all()
        )
        assert [n.id for n in remaining] == ["n3"]
