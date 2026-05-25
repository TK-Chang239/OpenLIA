"""Unit tests for InMemoryStateStore."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.persistence import (
    InMemoryStateStore,
    StateNotFoundError,
)
from openlia.llm.runtime.report_v2_3.schemas import Language, ReportType
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin


def _state(run_id: str = "r-1") -> ReportState:
    return ReportState(
        run_id=run_id,
        user_id="u",
        raw_prompt="p",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
    )


def test_save_then_load_round_trips_state() -> None:
    store = InMemoryStateStore()
    state = _state()
    store.save(state)
    loaded = store.load("r-1")
    assert loaded.run_id == "r-1"
    assert loaded.tickers == ["NVDA"]


def test_load_missing_raises_state_not_found() -> None:
    store = InMemoryStateStore()
    with pytest.raises(StateNotFoundError):
        store.load("ghost")


def test_save_overwrites_existing_state() -> None:
    store = InMemoryStateStore()
    s1 = _state()
    store.save(s1)
    s1.complete()
    store.save(s1)
    assert store.load("r-1").status.value == "complete"


def test_delete_removes_state() -> None:
    store = InMemoryStateStore()
    store.save(_state())
    assert "r-1" in store
    store.delete("r-1")
    assert "r-1" not in store
    with pytest.raises(StateNotFoundError):
        store.load("r-1")


def test_delete_is_idempotent() -> None:
    store = InMemoryStateStore()
    store.delete("never-saved")  # no raise
