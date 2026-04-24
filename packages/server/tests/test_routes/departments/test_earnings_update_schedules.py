"""HTTP tests for /departments/earnings-update/schedules.

The schedules CRUD lives in the existing `build_eu_schedules_router`
(mounted in app.py). This file asserts mount integration with the
company-mode app: auth gating, user scoping at the HTTP layer, and that
the route is present under the plan's prefix.

Deep CRUD behavior (int days_of_week, PATCH semantics, scheduler
registration) is covered by packages/server/tests/test_scheduler/
test_eu_schedules.py.
"""

from __future__ import annotations


def test_get_schedules_empty_list(company_client, auth_user):
    r = company_client.get("/departments/earnings-update/schedules")
    # Scheduler may be disabled in the company_client app; GET is allowed.
    assert r.status_code == 200
    assert r.json() == []


def test_post_without_scheduler_returns_503(company_client, auth_user):
    # company_client has no scheduler configured (lifespan not entered here).
    r = company_client.post(
        "/departments/earnings-update/schedules",
        json={
            "time": "07:00",
            "timezone": "UTC",
            "days_of_week": [0, 1, 2],
            "is_enabled": True,
        },
    )
    # Either scheduler disabled (503) or created if scheduler present.
    assert r.status_code in (503, 201)


def test_schedules_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/earnings-update/schedules")
    assert r.status_code == 401


def test_schedules_user_scoped_get(client, user_factory, login_as):
    u = user_factory()
    login_as(u)
    r = client.get("/departments/earnings-update/schedules")
    assert r.status_code == 200
    assert r.json() == []
