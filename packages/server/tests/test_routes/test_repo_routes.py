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
