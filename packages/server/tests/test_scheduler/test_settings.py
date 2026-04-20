from __future__ import annotations

import pytest
from openlia_server.scheduler.settings import SchedulerSettings


def test_defaults_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "OPENLIA_SCHEDULER_ENABLED",
        "OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS",
        "OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS",
    ):
        monkeypatch.delenv(k, raising=False)
    s = SchedulerSettings.from_env()
    assert s.enabled is True
    assert s.misfire_grace_seconds == 21_600
    assert s.shutdown_grace_seconds == 30


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
    ],
)
def test_enabled_parses_boolean_strings(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_ENABLED", raw)
    assert SchedulerSettings.from_env().enabled is expected


def test_grace_windows_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS", "3600")
    monkeypatch.setenv("OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS", "10")
    s = SchedulerSettings.from_env()
    assert s.misfire_grace_seconds == 3_600
    assert s.shutdown_grace_seconds == 10


def test_negative_grace_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS", "-1")
    with pytest.raises(ValueError, match="misfire_grace_seconds"):
        SchedulerSettings.from_env()


def test_malformed_integer_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS", "not-a-number")
    with pytest.raises(ValueError, match="shutdown_grace_seconds"):
        SchedulerSettings.from_env()
