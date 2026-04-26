"""Tests for the AI review schema, prompt builder, runner, and store."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from openlia.data.catalog import build_catalog
from openlia_server.ai_review.prompt import build_review_prompt
from openlia_server.ai_review.runner import run_review
from openlia_server.ai_review.schema import DepartmentReadiness, ReadinessState, ReviewResult
from openlia_server.ai_review.store import ReviewStore
from openlia_server.services.wizard_review import (
    _build_provider_payload,
    _try_deterministic_review,
)


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


# ---------------------------------------------------------------------------
# Catalog-grounded payload + deterministic short-circuit
# ---------------------------------------------------------------------------


def _row(*, id: str, kind: str, category: str = "financial", priority: int = 100) -> Any:  # noqa: A002
    return SimpleNamespace(
        id=id,
        kind=kind,
        category=category,
        priority=priority,
        extra_config={},
    )


def test_build_provider_payload_attaches_declared_capabilities_for_known_kinds() -> None:
    catalog = build_catalog()
    payload = _build_provider_payload([_row(id="p1", kind="eodhd")], catalog)
    assert payload[0]["unknown"] is False
    assert "stock_quote" in payload[0]["declared_capabilities"]


def test_build_provider_payload_marks_unknown_kinds() -> None:
    catalog = build_catalog()
    payload = _build_provider_payload([_row(id="p1", kind="polygon_io")], catalog)
    assert payload[0]["unknown"] is True
    assert payload[0]["declared_capabilities"] == []


def test_build_provider_payload_surfaces_social_capabilities_for_known_kind() -> None:
    catalog = build_catalog()
    payload = _build_provider_payload(
        [_row(id="p1", kind="reddit", category="social_media")], catalog
    )
    assert payload[0]["unknown"] is False
    assert "social_sentiment" in payload[0]["declared_capabilities"]


def test_deterministic_review_returns_ready_when_basics_covered() -> None:
    providers = [
        {
            "id": "p1",
            "kind": "eodhd",
            "provider": "eodhd",
            "declared_capabilities": ["stock_quote", "company_news"],
            "unknown": False,
        }
    ]
    result = _try_deterministic_review(
        departments=[("secretary", ["stock_quote", "company_news"])],
        providers=providers,
    )
    assert result is not None
    assert result.departments[0].state == ReadinessState.READY
    assert result.departments[0].unmet == []
    assert all(m.confidence == 1.0 for m in result.departments[0].basic)


def test_deterministic_review_returns_blocked_when_basic_unmet() -> None:
    providers = [
        {
            "id": "p1",
            "kind": "fmp",
            "provider": "fmp",
            "declared_capabilities": ["stock_quote"],
            "unknown": False,
        }
    ]
    result = _try_deterministic_review(
        departments=[("equity_research", ["stock_quote", "company_news"])],
        providers=providers,
    )
    assert result is not None
    assert result.departments[0].state == ReadinessState.BLOCKED
    assert result.departments[0].unmet == ["company_news"]


def test_deterministic_review_falls_back_to_llm_when_unknown_provider_present() -> None:
    providers = [
        {
            "id": "p1",
            "kind": "polygon_io",
            "provider": "polygon_io",
            "declared_capabilities": [],
            "unknown": True,
        }
    ]
    result = _try_deterministic_review(
        departments=[("secretary", ["stock_quote"])],
        providers=providers,
    )
    assert result is None


def test_deterministic_review_summary_counts_ready() -> None:
    providers = [
        {
            "id": "p1",
            "kind": "eodhd",
            "provider": "eodhd",
            "declared_capabilities": ["stock_quote"],
            "unknown": False,
        }
    ]
    result = _try_deterministic_review(
        departments=[
            ("secretary", ["stock_quote"]),
            ("equity_research", ["company_news"]),
        ],
        providers=providers,
    )
    assert result is not None
    assert result.summary == "1 of 2 ready."


# ---------------------------------------------------------------------------
# Prompt grounding
# ---------------------------------------------------------------------------


def test_review_prompt_carries_grounding_rules_and_unknown_marker() -> None:
    prompt = build_review_prompt(
        departments=[("secretary", ["stock_quote"])],
        providers=[
            {
                "id": "p1",
                "kind": "eodhd",
                "provider": "eodhd",
                "declared_capabilities": ["stock_quote"],
                "unknown": False,
            },
            {
                "id": "p2",
                "kind": "polygon_io",
                "provider": "polygon_io",
                "declared_capabilities": [],
                "unknown": True,
            },
        ],
    )
    assert "declared_capabilities" in prompt
    assert "unknown" in prompt
    assert "0.5" in prompt
    assert "polygon_io" in prompt
