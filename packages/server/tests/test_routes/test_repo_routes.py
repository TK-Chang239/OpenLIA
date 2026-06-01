"""Route tests for /repo/items save/unsave."""

from __future__ import annotations


def test_save_then_list(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r = report_factory(user_id=u.id)
    resp = client.post("/repo/items", json={"report_id": r.id})
    assert resp.status_code == 201
    assert client.get("/repo/items").json()["items"][0]["report_id"] == r.id


def test_save_twice_is_idempotent(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r = report_factory(user_id=u.id)
    first = client.post("/repo/items", json={"report_id": r.id}).json()
    second = client.post("/repo/items", json={"report_id": r.id}).json()
    assert first["id"] == second["id"]


def test_delete_by_report_id(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r = report_factory(user_id=u.id)
    client.post("/repo/items", json={"report_id": r.id})
    assert client.delete(f"/repo/items?report_id={r.id}").status_code == 204
    assert client.get("/repo/items").json()["items"] == []


def test_delete_when_absent_is_idempotent(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r = report_factory(user_id=u.id)
    assert client.delete(f"/repo/items?report_id={r.id}").status_code == 204


def test_save_unknown_report_returns_404(client, user_factory, login_as):
    login_as(user_factory())
    resp = client.post("/repo/items", json={"report_id": "nonexistent"})
    assert resp.status_code == 404


def test_list_scoped_to_user(client, user_factory, login_as, report_factory):
    a = user_factory()
    b = user_factory()
    login_as(a)
    ra = report_factory(user_id=a.id)
    client.post("/repo/items", json={"report_id": ra.id})
    login_as(b)
    assert client.get("/repo/items").json()["items"] == []


# ---------------------------------------------------------------------------
# v3 polymorphic-target routes (PR8)
# ---------------------------------------------------------------------------


def _v3_report_factory(db_session):
    import uuid
    from datetime import UTC, datetime

    from openlia_server.db.models.report_v3 import ReportV3

    def _make(user_id: str, **kwargs):
        r = ReportV3(
            id=str(uuid.uuid4()),
            user_id=user_id,
            subject=kwargs.get("subject", "RKLB.US"),
            template_id=kwargs.get("template_id", "initiation_default"),
            language="en",
            length="normal",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="completed",
            error_message=None,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db_session.add(r)
        db_session.commit()
        return r

    return _make


def test_v3_save_then_list(client, user_factory, login_as, db_session):
    u = user_factory()
    login_as(u)
    r = _v3_report_factory(db_session)(user_id=u.id)
    resp = client.post("/repo/v3-runs", json={"v3_report_id": r.id})
    assert resp.status_code == 201
    listed = client.get("/repo/v3-runs").json()
    assert listed["saved_report_ids"] == [r.id]


def test_v3_save_twice_idempotent(client, user_factory, login_as, db_session):
    u = user_factory()
    login_as(u)
    r = _v3_report_factory(db_session)(user_id=u.id)
    first = client.post("/repo/v3-runs", json={"v3_report_id": r.id}).json()
    second = client.post("/repo/v3-runs", json={"v3_report_id": r.id}).json()
    assert first["id"] == second["id"]


def test_v3_delete_removes_entry(client, user_factory, login_as, db_session):
    u = user_factory()
    login_as(u)
    r = _v3_report_factory(db_session)(user_id=u.id)
    client.post("/repo/v3-runs", json={"v3_report_id": r.id})
    assert client.delete(f"/repo/v3-runs?v3_report_id={r.id}").status_code == 204
    assert client.get("/repo/v3-runs").json()["saved_report_ids"] == []


def test_v3_save_unknown_returns_404(client, user_factory, login_as):
    login_as(user_factory())
    resp = client.post("/repo/v3-runs", json={"v3_report_id": "missing"})
    assert resp.status_code == 404


def test_v3_save_other_users_report_returns_404(client, user_factory, login_as, db_session):
    owner = user_factory()
    intruder = user_factory()
    r = _v3_report_factory(db_session)(user_id=owner.id)
    login_as(intruder)
    resp = client.post("/repo/v3-runs", json={"v3_report_id": r.id})
    assert resp.status_code == 404


def test_v3_list_excludes_v1_and_v2_saves(
    client, user_factory, login_as, db_session, report_factory
):
    u = user_factory()
    login_as(u)
    v1 = report_factory(user_id=u.id)
    v3 = _v3_report_factory(db_session)(user_id=u.id)
    client.post("/repo/items", json={"report_id": v1.id})
    client.post("/repo/v3-runs", json={"v3_report_id": v3.id})
    # /v3-runs only returns v3 ids
    assert client.get("/repo/v3-runs").json()["saved_report_ids"] == [v3.id]
    # /items still returns v1 (existing surface unchanged)
    v1_items = [i for i in client.get("/repo/items").json()["items"] if i["report_id"] == v1.id]
    assert len(v1_items) == 1


# ---------------------------------------------------------------------------
# Earnings Update v2 polymorphic-target routes
# ---------------------------------------------------------------------------


def _eu_report_factory(db_session):
    import uuid
    from datetime import UTC, datetime

    from openlia_server.db.models.report_eu import ReportEu

    def _make(user_id: str, **kwargs):
        r = ReportEu(
            id=str(uuid.uuid4()),
            user_id=user_id,
            subject=kwargs.get("subject", "RKLB.US"),
            ticker=kwargs.get("ticker", "RKLB.US"),
            trigger_kind="on_demand",
            fiscal_date=None,
            template_id="eu_default",
            language="en",
            length="normal",
            provider_kind="anthropic",
            model="m",
            status="completed",
            error_message=None,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            cover_json=None,
            reasoning_effort=None,
        )
        db_session.add(r)
        db_session.commit()
        return r

    return _make


def test_eu_save_then_list(client, user_factory, login_as, db_session):
    u = user_factory()
    login_as(u)
    r = _eu_report_factory(db_session)(user_id=u.id)
    resp = client.post("/repo/eu-runs", json={"eu_v2_report_id": r.id})
    assert resp.status_code == 201
    assert resp.json()["eu_v2_report_id"] == r.id
    listed = client.get("/repo/eu-runs").json()
    assert listed["saved_report_ids"] == [r.id]


def test_eu_delete_removes_entry(client, user_factory, login_as, db_session):
    u = user_factory()
    login_as(u)
    r = _eu_report_factory(db_session)(user_id=u.id)
    client.post("/repo/eu-runs", json={"eu_v2_report_id": r.id})
    assert client.delete(f"/repo/eu-runs?eu_v2_report_id={r.id}").status_code == 204
    assert client.get("/repo/eu-runs").json()["saved_report_ids"] == []


def test_eu_save_unknown_returns_404(client, user_factory, login_as):
    login_as(user_factory())
    resp = client.post("/repo/eu-runs", json={"eu_v2_report_id": "missing"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "eu_report_not_found"
