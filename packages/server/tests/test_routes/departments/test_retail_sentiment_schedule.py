"""HTTP tests for /departments/retail_sentiment/schedule (RS_SNAPSHOT job)."""

from __future__ import annotations


def test_get_schedule_returns_null_when_missing(company_client, auth_user):
    r = company_client.get("/departments/retail_sentiment/schedule")
    assert r.status_code == 200
    assert r.json() == {"schedule": None}


def test_put_schedule_without_scheduler_returns_503(company_client, auth_user):
    r = company_client.put(
        "/departments/retail_sentiment/schedule",
        json={
            "time": "08:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "label": "Open",
        },
    )
    # Without lifespan, scheduler is unset → 503.
    assert r.status_code == 503


def test_put_schedule_rejects_invalid_time(company_client, auth_user):
    r = company_client.put(
        "/departments/retail_sentiment/schedule",
        json={
            "time": "99:99",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "bad",
        },
    )
    assert r.status_code == 422


def test_put_schedule_rejects_invalid_day(company_client, auth_user):
    r = company_client.put(
        "/departments/retail_sentiment/schedule",
        json={
            "time": "08:00",
            "timezone": "America/New_York",
            "days_of_week": ["funday"],
            "label": "bad",
        },
    )
    assert r.status_code == 422


def test_get_schedule_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/retail_sentiment/schedule")
    assert r.status_code == 401


def test_put_schedule_requires_auth(company_client_anon):
    r = company_client_anon.put(
        "/departments/retail_sentiment/schedule",
        json={
            "time": "08:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "x",
        },
    )
    assert r.status_code == 401


def test_put_schedule_create_replace_disable_with_fake_scheduler(company_client, auth_user) -> None:
    """Wire a fake scheduler into app.state and exercise the upsert path."""

    class _FakeScheduler:
        def __init__(self) -> None:
            self.added: list[str] = []
            self.modified: list[str] = []
            self.removed: list[tuple[str, str]] = []

        async def add_schedule(self, schedule) -> None:
            self.added.append(schedule.id)

        async def modify_schedule(self, schedule) -> None:
            self.modified.append(schedule.id)

        async def remove_schedule(self, *, job_type, user_id) -> None:
            self.removed.append((job_type.value, user_id))

    fake = _FakeScheduler()
    company_client.app.state.scheduler = fake

    # CREATE
    r = company_client.put(
        "/departments/retail_sentiment/schedule",
        json={
            "time": "08:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "label": "Open",
        },
    )
    assert r.status_code == 200
    body = r.json()
    sched_id = body["id"]
    assert body["time"] == "08:00"
    assert body["is_enabled"] is True
    assert fake.added == [sched_id]
    assert fake.modified == []

    # READ
    r2 = company_client.get("/departments/retail_sentiment/schedule")
    assert r2.status_code == 200
    assert r2.json()["schedule"]["id"] == sched_id

    # REPLACE (same user → modify, not add)
    r3 = company_client.put(
        "/departments/retail_sentiment/schedule",
        json={
            "time": "09:30",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "Late Open",
        },
    )
    assert r3.status_code == 200
    assert r3.json()["time"] == "09:30"
    assert fake.modified == [sched_id]

    # DISABLE via PUT
    r4 = company_client.put(
        "/departments/retail_sentiment/schedule",
        json={
            "time": "09:30",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "Late Open",
            "is_enabled": False,
        },
    )
    assert r4.status_code == 200
    assert r4.json()["is_enabled"] is False
    assert ("rs_snapshot", auth_user.id) in fake.removed
