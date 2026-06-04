"""Tests for `openlia_server.services.runtime.run_department` entry point.

Phase 9.3: a single dispatch entry that selects chat vs deterministic
by inspecting `dept.requires_runner` plus the caller's mode.

Note: after the Macro Research (#251) and Retail Sentiment dashboard
migrations, NO registered department sets `requires_runner=True` — both
dashboards are routed via their own routes/scheduler, not this picker. The
runner-branch tests therefore exercise `select_runtime_mode` against a
synthetic runner dept so coverage of that branch survives the migration.
"""

from __future__ import annotations

import pytest
from openlia_server.services import runtime as runtime_mod
from openlia_server.services.runtime import (
    RuntimeModeMismatchError,
    UnknownDepartmentError,
    run_department,
    select_runtime_mode,
)


class _FakeRunnerDept:
    """Stand-in deterministic-runner department (no real dept is one today)."""

    requires_runner = True


@pytest.fixture
def _runner_dept(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `get_department(...)` resolve to a synthetic runner dept."""
    monkeypatch.setattr(runtime_mod, "get_department", lambda department_id: _FakeRunnerDept())


def test_select_mode_chat_default_for_chat_only_dept() -> None:
    assert select_runtime_mode(department_id="secretary", requested=None) == "chat"


def test_select_mode_deterministic_default_for_runner_dept(_runner_dept: None) -> None:
    assert select_runtime_mode(department_id="x_runner", requested=None) == "deterministic"


def test_select_mode_explicit_chat_allowed_on_chat_dept() -> None:
    assert select_runtime_mode(department_id="secretary", requested="chat") == "chat"


def test_select_mode_scheduled_chat_allowed_on_pt_mb() -> None:
    assert (
        select_runtime_mode(department_id="panic_thermometer", requested="scheduled_chat")
        == "scheduled_chat"
    )
    assert (
        select_runtime_mode(department_id="morning_briefing", requested="scheduled_chat")
        == "scheduled_chat"
    )


def test_select_mode_rejects_chat_on_runner_dept(_runner_dept: None) -> None:
    with pytest.raises(RuntimeModeMismatchError):
        select_runtime_mode(department_id="x_runner", requested="chat")
    with pytest.raises(RuntimeModeMismatchError):
        select_runtime_mode(department_id="x_runner", requested="scheduled_chat")


def test_select_mode_rejects_deterministic_on_chat_dept() -> None:
    with pytest.raises(RuntimeModeMismatchError):
        select_runtime_mode(department_id="secretary", requested="deterministic")


def test_select_mode_retail_sentiment_is_now_chat_not_runner() -> None:
    # RS migrated to a web-search dashboard (requires_runner=False); it is no
    # longer a deterministic runner. It routes via its own dashboard routes,
    # so this picker simply treats it as non-runner (chat default).
    assert select_runtime_mode(department_id="retail_sentiment", requested=None) == "chat"


def test_select_mode_unknown_department_raises() -> None:
    with pytest.raises(UnknownDepartmentError):
        select_runtime_mode(department_id="not_a_real_dept", requested=None)


def test_run_department_deterministic_returns_descriptor(_runner_dept: None) -> None:
    """Deterministic depts surface a transparent descriptor; the actual
    runners are wired by the scheduler executors."""

    class _Req:
        ticker = "AAPL"

    out = run_department(
        department_id="x_runner",
        mode=None,
        request=_Req(),
        db_session_factory=lambda: None,
    )
    assert out["mode"] == "deterministic"
    assert out["department_id"] == "x_runner"
    assert out["request"] is not None
