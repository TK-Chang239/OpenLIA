"""HTTP tests for POST /departments/morning-briefing/chat/session."""

from __future__ import annotations


def test_resolves_or_creates_session(company_client, auth_user):
    r = company_client.post("/departments/morning-briefing/chat/session")
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert len(sid) == 36

    r2 = company_client.post("/departments/morning-briefing/chat/session")
    assert r2.json()["session_id"] == sid


def test_session_department_is_morning_briefing(company_client, auth_user, db_session):
    from openlia_server.db.models.content import ChatSession

    sid = company_client.post(
        "/departments/morning-briefing/chat/session"
    ).json()["session_id"]
    row = db_session.query(ChatSession).filter_by(id=sid).one()
    assert row.department == "morning_briefing"
    assert row.user_id == auth_user.id


def test_session_is_user_scoped(client, user_factory, login_as):
    u1 = user_factory()
    u2 = user_factory()
    login_as(u1)
    sid_1 = client.post("/departments/morning-briefing/chat/session").json()[
        "session_id"
    ]
    login_as(u2)
    sid_2 = client.post("/departments/morning-briefing/chat/session").json()[
        "session_id"
    ]
    assert sid_1 != sid_2


def test_session_requires_auth(company_client_anon):
    r = company_client_anon.post("/departments/morning-briefing/chat/session")
    assert r.status_code == 401
