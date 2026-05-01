"""Tests for `openlia_server.services.runtime.run_department` entry point.

Phase 9.3: a single dispatch entry that selects chat vs deterministic
by inspecting `dept.requires_runner` plus the caller's mode.
"""

from __future__ import annotations

import pytest
from openlia_server.services.runtime import (
    RuntimeModeMismatchError,
    UnknownDepartmentError,
    run_department,
    select_runtime_mode,
)


def test_select_mode_chat_default_for_chat_only_dept() -> None:
    assert select_runtime_mode(department_id="secretary", requested=None) == "chat"


def test_select_mode_deterministic_default_for_runner_dept() -> None:
    assert select_runtime_mode(department_id="macro_research", requested=None) == "deterministic"
    assert select_runtime_mode(department_id="retail_sentiment", requested=None) == "deterministic"


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


def test_select_mode_rejects_chat_on_runner_dept() -> None:
    with pytest.raises(RuntimeModeMismatchError):
        select_runtime_mode(department_id="macro_research", requested="chat")
    with pytest.raises(RuntimeModeMismatchError):
        select_runtime_mode(department_id="macro_research", requested="scheduled_chat")


def test_select_mode_rejects_deterministic_on_chat_dept() -> None:
    with pytest.raises(RuntimeModeMismatchError):
        select_runtime_mode(department_id="secretary", requested="deterministic")


def test_select_mode_unknown_department_raises() -> None:
    with pytest.raises(UnknownDepartmentError):
        select_runtime_mode(department_id="not_a_real_dept", requested=None)


def test_run_department_deterministic_returns_descriptor() -> None:
    """Deterministic depts surface a transparent descriptor; the actual
    MR/RS runners are wired by the scheduler executors."""

    class _Req:
        ticker = "AAPL"

    out = run_department(
        department_id="retail_sentiment",
        mode=None,
        request=_Req(),
        db_session_factory=lambda: None,
    )
    assert out["mode"] == "deterministic"
    assert out["department_id"] == "retail_sentiment"
    assert out["request"] is not None
