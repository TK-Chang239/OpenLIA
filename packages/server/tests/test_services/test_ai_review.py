"""Tests for the AI review schema, prompt builder, runner, and store."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from openlia_server.ai_review.prompt import build_review_prompt
from openlia_server.ai_review.runner import run_review
from openlia_server.ai_review.schema import DepartmentReadiness, ReadinessState, ReviewResult
from openlia_server.ai_review.store import ReviewStore


def test_readiness_state_values() -> None:
    assert set(s.value for s in ReadinessState) == {"ready", "gaps", "disabled", "blocked"}


def test_review_result_serializes() -> None:
    result = ReviewResult(
        summary="6 of 7 ready.",
        departments=[
            DepartmentReadiness(
                id="secretary",
                state=ReadinessState.READY,
                note=None,
                basic=[{"type": "stock_quote", "provider": "eodhd", "confidence": 0.95}],
                advanced=[],
                unmet=[],
            )
        ],
    )
    dumped = result.model_dump()
    assert dumped["departments"][0]["state"] == "ready"


def test_build_review_prompt_lists_departments_and_providers() -> None:
    prompt = build_review_prompt(
        departments=[("secretary", ["stock_quote"])],
        providers=[{"id": "p1", "category": "financial", "provider": "eodhd"}],
    )
    assert "secretary" in prompt
    assert "stock_quote" in prompt
    assert "eodhd" in prompt
    assert "confidence" in prompt


@pytest.mark.asyncio
async def test_run_review_populates_store_on_success(db_session) -> None:
    store = ReviewStore()
    review_id = store.create()

    fake_llm = AsyncMock()
    fake_llm.generate.return_value = type(
        "Response",
        (),
        {
            "text": '{"summary": "1 of 1 ready.", "departments": ['
            '{"id": "secretary", "state": "ready", "note": null, '
            '"basic": [{"type": "stock_quote", "provider": "eodhd", "confidence": 0.9}], '
            '"advanced": [], "unmet": []}]}'
        },
    )()

    await run_review(
        review_id=review_id,
        db=db_session,
        llm=fake_llm,
        departments=[("secretary", ["stock_quote"])],
        providers=[{"id": "p1", "category": "financial", "provider": "eodhd"}],
        store=store,
    )
    entry = store.get(review_id)
    assert entry is not None
    assert entry["state"] == "complete"
    assert entry["result"]["departments"][0]["state"] == "ready"


@pytest.mark.asyncio
async def test_run_review_marks_failure_on_bad_json() -> None:
    store = ReviewStore()
    review_id = store.create()

    fake_llm = AsyncMock()
    fake_llm.generate.return_value = type("R", (), {"text": "not json"})()

    await run_review(
        review_id=review_id,
        db=None,
        llm=fake_llm,
        departments=[("secretary", ["stock_quote"])],
        providers=[],
        store=store,
    )
    entry = store.get(review_id)
    assert entry["state"] == "failed"
    assert "parse" in entry["error"].lower()
