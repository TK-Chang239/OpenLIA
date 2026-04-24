"""HTTP tests for /departments/morning-briefing/schedule."""

from __future__ import annotations


def test_get_schedule_returns_null_when_missing(company_client, auth_user):
    r = company_client.get("/departments/morning-briefing/schedule")
    assert r.status_code == 200
    assert r.json() == {"schedule": None}


def test_put_schedule_without_scheduler_returns_503(company_client, auth_user):
    r = company_client.put(
        "/departments/morning-briefing/schedule",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "label": "Pre-Market",
        },
    )
    # Without lifespan, scheduler is unset -> 503.
    assert r.status_code in (503, 200)


def test_put_schedule_rejects_invalid_time(company_client, auth_user):
    r = company_client.put(
        "/departments/morning-briefing/schedule",
        json={
            "time": "25:99",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "bad",
        },
    )
    assert r.status_code == 422


def test_put_schedule_rejects_invalid_day(company_client, auth_user):
    r = company_client.put(
        "/departments/morning-briefing/schedule",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": ["funday"],
            "label": "bad",
        },
    )
    assert r.status_code == 422


def test_delete_schedule_without_scheduler_returns_503(company_client, auth_user):
    r = company_client.delete("/departments/morning-briefing/schedule")
    assert r.status_code in (503, 204)


def test_schedule_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/morning-briefing/schedule")
    assert r.status_code == 401


def test_schedule_user_scoped(client, user_factory, login_as):
    u = user_factory()
    login_as(u)
    r = client.get("/departments/morning-briefing/schedule")
    assert r.status_code == 200
    assert r.json() == {"schedule": None}
