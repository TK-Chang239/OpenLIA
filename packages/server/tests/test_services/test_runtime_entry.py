"""Tests for `openlia_server.services.runtime.run_department` entry point.

All departments are chat-flow. `select_runtime_mode` resolves `chat` or
`scheduled_chat`; `deterministic` raises `RuntimeModeMismatchError`.
"""

from __future__ import annotations

import pytest
from openlia_server.services.runtime import (
    RuntimeModeMismatchError,
    UnknownDepartmentError,
    select_runtime_mode,
)


def test_select_mode_chat_default_for_chat_only_dept() -> None:
    assert select_runtime_mode(department_id="secretary", requested=None) == "chat"


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


def test_select_mode_rejects_deterministic_on_chat_dept() -> None:
    with pytest.raises(RuntimeModeMismatchError):
        select_runtime_mode(department_id="secretary", requested="deterministic")


def test_select_mode_retail_sentiment_is_now_chat_not_runner() -> None:
    # RS migrated to a web-search dashboard; it is no longer a deterministic runner.
    assert select_runtime_mode(department_id="retail_sentiment", requested=None) == "chat"


def test_select_mode_unknown_department_raises() -> None:
    with pytest.raises(UnknownDepartmentError):
        select_runtime_mode(department_id="not_a_real_dept", requested=None)
