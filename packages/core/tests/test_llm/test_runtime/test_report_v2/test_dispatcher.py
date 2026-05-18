# packages/core/tests/test_llm/test_runtime/test_report_v2/test_dispatcher.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from openlia.llm.runtime.report_v2.packer.validator import ValidationFinding
from openlia.llm.runtime.report_v2.sections.dispatcher import SectionDispatch, dispatch_sections
from openlia.llm.runtime.report_v2.types import SectionTerminalState

GOOD_MD = (
    """---
section_id: company_overview
title: Company Overview
sources_used: [1]
---

## Company Overview

The company exists [1]. """
    + " ".join(["word"] * 500)
    + """
"""
)

TINY_MD = """---
section_id: company_overview
title: Company Overview
sources_used: [1]
---

## Body

Tiny.
"""


def _validator_factory(*, fail_on_attempt):
    calls = {"n": 0}

    def _validate(parsed, *, facts_slice, target_word_count):
        calls["n"] += 1
        if calls["n"] <= fail_on_attempt:
            return [
                ValidationFinding(check="word_count_minimum", section_id="x", detail="too short")
            ]
        return []

    return _validate


@pytest.mark.asyncio
async def test_dispatch_single_section_success() -> None:
    writer = AsyncMock()
    writer.write.return_value = GOOD_MD
    dispatch = SectionDispatch(
        section_id="company_overview",
        prompt="...",
        target_word_count=600,
        facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch],
        writer=writer,
        validator=lambda p, **kw: [],
        max_retries=1,
        known_block_tags=["text", "table"],
    )
    assert len(results) == 1
    assert results[0].state == SectionTerminalState.SUCCESS
    assert results[0].attempts == 1


@pytest.mark.asyncio
async def test_dispatch_retries_with_structured_error_then_succeeds() -> None:
    writer = AsyncMock()
    writer.write.side_effect = [TINY_MD, GOOD_MD]
    validator = _validator_factory(fail_on_attempt=1)
    dispatch = SectionDispatch(
        section_id="company_overview",
        prompt="...",
        target_word_count=600,
        facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch],
        writer=writer,
        validator=validator,
        max_retries=1,
        known_block_tags=["text"],
    )
    assert results[0].state == SectionTerminalState.DEGRADED
    assert results[0].attempts == 2


@pytest.mark.asyncio
async def test_dispatch_exhaustion_returns_terminal_state() -> None:
    writer = AsyncMock()
    writer.write.return_value = TINY_MD
    validator = _validator_factory(fail_on_attempt=99)
    dispatch = SectionDispatch(
        section_id="company_overview",
        prompt="...",
        target_word_count=600,
        facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch],
        writer=writer,
        validator=validator,
        max_retries=1,
        known_block_tags=["text"],
    )
    assert results[0].state == SectionTerminalState.EXHAUSTED
    assert results[0].attempts == 2
    assert len(results[0].failed_attempts) == 2


@pytest.mark.asyncio
async def test_dispatch_runs_sections_in_parallel() -> None:
    writer = AsyncMock()
    writer.write.return_value = GOOD_MD
    dispatches = [
        SectionDispatch(section_id=f"s{i}", prompt="x", target_word_count=600, facts_slice={})
        for i in range(5)
    ]
    results = await dispatch_sections(
        dispatches=dispatches,
        writer=writer,
        validator=lambda p, **kw: [],
        max_retries=1,
        known_block_tags=["text"],
    )
    assert len(results) == 5
    assert writer.write.await_count == 5


@pytest.mark.asyncio
async def test_dispatch_respects_concurrency_semaphore() -> None:
    """At most 2 concurrent write() calls in flight when Semaphore(2) is passed."""
    import asyncio

    max_concurrent = 0
    current_concurrent = 0

    async def _tracked_write(prompt: str) -> str:
        nonlocal max_concurrent, current_concurrent
        current_concurrent += 1
        if current_concurrent > max_concurrent:
            max_concurrent = current_concurrent
        await asyncio.sleep(0)  # yield to let other coroutines attempt to acquire
        current_concurrent -= 1
        return GOOD_MD

    writer = AsyncMock()
    writer.write.side_effect = _tracked_write

    dispatches = [
        SectionDispatch(section_id=f"s{i}", prompt="x", target_word_count=600, facts_slice={})
        for i in range(10)
    ]
    semaphore = asyncio.Semaphore(2)
    results = await dispatch_sections(
        dispatches=dispatches,
        writer=writer,
        validator=lambda p, **kw: [],
        max_retries=1,
        known_block_tags=["text"],
        concurrency_semaphore=semaphore,
    )
    assert len(results) == 10
    assert writer.write.await_count == 10
    assert max_concurrent <= 2
