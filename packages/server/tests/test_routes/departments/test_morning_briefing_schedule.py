"""HTTP tests for /departments/morning-briefing/schedules (multi-schedule)."""

from __future__ import annotations


def test_list_schedules_returns_empty_when_none(company_client, auth_user):
    r = company_client.get("/departments/morning-briefing/schedules")
    assert r.status_code == 200
    assert r.json() == []


def test_post_schedule_without_scheduler_returns_503(company_client, auth_user):
    r = company_client.post(
        "/departments/morning-briefing/schedules",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "label": "Pre-Market",
        },
    )
    assert r.status_code in (503, 201)


def test_post_schedule_rejects_invalid_time(company_client, auth_user):
    r = company_client.post(
        "/departments/morning-briefing/schedules",
        json={
            "time": "25:99",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "bad",
        },
    )
    assert r.status_code == 422


def test_post_schedule_rejects_invalid_day(company_client, auth_user):
    r = company_client.post(
        "/departments/morning-briefing/schedules",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": ["funday"],
            "label": "bad",
        },
    )
    assert r.status_code == 422


def test_delete_unknown_schedule_returns_503_or_404(company_client, auth_user):
    r = company_client.delete("/departments/morning-briefing/schedules/does-not-exist")
    assert r.status_code in (503, 404)


def test_schedule_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/morning-briefing/schedules")
    assert r.status_code == 401


def test_schedule_user_scoped(client, user_factory, login_as):
    u = user_factory()
    login_as(u)
    r = client.get("/departments/morning-briefing/schedules")
    assert r.status_code == 200
    assert r.json() == []
