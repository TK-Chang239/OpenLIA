"""Tests for stage 4 gather — strand dispatcher with retry-once and cache-stat aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from openlia.llm.runtime.report_v2.pipeline.stage_4_gather import StrandDispatcher
from openlia.llm.runtime.report_v2.schemas.plan import ResearchStrand

_NOW = datetime(2026, 5, 21, tzinfo=UTC)

_CITATION_DICT = {
    "id": "c1",
    "source_type": "tool_call",
    "tool": "eodhd",
    "url": None,
    "title": "AAPL Financials",
    "retrieved_at": _NOW,
    "snippet": "Revenue up 10%",
}


def _strand(strand_id: str) -> ResearchStrand:
    return ResearchStrand(id=strand_id, purpose="research purpose")


def test_strand_dispatcher_runs_each_strand_and_aggregates() -> None:
    strand_a = _strand("a")
    strand_b = _strand("b")

    subagent = Mock()
    subagent.run.side_effect = [
        {"findings": "findings-a", "citations": [_CITATION_DICT]},
        {"findings": "findings-b", "citations": [_CITATION_DICT]},
    ]

    dispatcher = StrandDispatcher(subagent=subagent, max_workers=2)
    plan = Mock()
    pool = dispatcher.dispatch([strand_a, strand_b], composer_inputs={}, plan=plan)

    assert pool.findings_by_strand["a"] == "findings-a"
    assert pool.findings_by_strand["b"] == "findings-b"
    assert len(pool.citations) == 2
    assert pool.failed_strands == []


def test_strand_failure_retries_once_then_marks_failed() -> None:
    strand_a = _strand("fail-me")

    subagent = Mock()
    subagent.run.side_effect = [RuntimeError("boom"), RuntimeError("boom again")]

    dispatcher = StrandDispatcher(subagent=subagent, max_workers=1)
    plan = Mock()
    pool = dispatcher.dispatch([strand_a], composer_inputs={}, plan=plan)

    assert "fail-me" in pool.failed_strands
    assert subagent.run.call_count == 2


def test_strand_failure_retries_once_then_succeeds() -> None:
    strand_a = _strand("retry-ok")

    subagent = Mock()
    subagent.run.side_effect = [
        RuntimeError("first attempt fails"),
        {"findings": "ok", "citations": []},
    ]

    dispatcher = StrandDispatcher(subagent=subagent, max_workers=1)
    plan = Mock()
    pool = dispatcher.dispatch([strand_a], composer_inputs={}, plan=plan)

    assert pool.findings_by_strand["retry-ok"] == "ok"
    assert "retry-ok" not in pool.failed_strands
    assert subagent.run.call_count == 2


def test_cache_stats_accumulated() -> None:
    strand_a = _strand("cache-strand")

    subagent = Mock()
    subagent.run.return_value = {
        "findings": "some findings",
        "citations": [],
        "cache_hits": 3,
        "cache_misses": 1,
    }

    dispatcher = StrandDispatcher(subagent=subagent, max_workers=1)
    plan = Mock()
    pool = dispatcher.dispatch([strand_a], composer_inputs={}, plan=plan)

    assert pool.cache_hits == 3
    assert pool.cache_misses == 1
