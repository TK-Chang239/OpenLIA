"""Slice 12 — core declaration of the ``recall_artifacts`` LLM tool.

The schema lives in core so chat-style departments can advertise it via
the dispatcher; the handler is server-side (it needs DB + embedding
provider) and is injected into ``ChatRunner``. These tests cover the
schema shape, the top_k clamp, the empty-result contract, and the
tenant-isolation guarantee that ``user_id`` is sourced only from the
runtime context.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.recall_artifacts import (
    MAX_TOP_K,
    RECALL_ARTIFACTS_SCHEMA,
    RECALL_ARTIFACTS_TOOL_NAME,
    _clamp_top_k,
    dispatch_recall_artifacts,
)


def test_schema_shape() -> None:
    assert RECALL_ARTIFACTS_SCHEMA.name == RECALL_ARTIFACTS_TOOL_NAME
    props = RECALL_ARTIFACTS_SCHEMA.parameters["properties"]
    assert set(props.keys()) == {"query", "top_k"}
    assert RECALL_ARTIFACTS_SCHEMA.parameters["required"] == ["query"]
    assert RECALL_ARTIFACTS_SCHEMA.parameters["additionalProperties"] is False
    assert props["top_k"]["maximum"] == MAX_TOP_K


def test_clamp_top_k_bounds() -> None:
    assert _clamp_top_k(0) == 1
    assert _clamp_top_k(1) == 1
    assert _clamp_top_k(5) == 5
    assert _clamp_top_k(MAX_TOP_K) == MAX_TOP_K
    assert _clamp_top_k(MAX_TOP_K + 50) == MAX_TOP_K
    assert _clamp_top_k(-3) == 1
    # Non-integers fall back to the schema default.
    assert _clamp_top_k(None) == 5
    assert _clamp_top_k("seven") == 5
    assert _clamp_top_k(True) == 5  # bool subclass — explicit reject
    assert _clamp_top_k(3.0) == 3  # integral float ok
    assert _clamp_top_k(3.7) == 5  # non-integral float -> default


@pytest.mark.asyncio
async def test_dispatch_passes_user_id_from_context_not_args() -> None:
    """The handler must receive the runtime-context user_id, never an
    LLM-supplied override. Cross-tenant recall would be a data leak."""
    captured: dict[str, object] = {}

    async def handler(user_id: str | None, query: str, top_k: int):
        captured["user_id"] = user_id
        captured["query"] = query
        captured["top_k"] = top_k
        return [{"id": "r1", "subject": "NVDA", "tagline": "tag", "score": 0.9}]

    # The LLM tries to spoof another user; we must ignore it.
    result = await dispatch_recall_artifacts(
        handler,
        user_id="real-user",
        arguments={"query": "nvidia thesis", "top_k": 3, "user_id": "victim"},
        call_id="c1",
    )

    assert captured["user_id"] == "real-user"
    assert captured["query"] == "nvidia thesis"
    assert captured["top_k"] == 3
    assert result.ok
    assert result.payload["results"][0]["subject"] == "NVDA"


@pytest.mark.asyncio
async def test_dispatch_empty_results_ok_not_error() -> None:
    async def handler(user_id, query, top_k):
        return []

    result = await dispatch_recall_artifacts(
        handler,
        user_id="u1",
        arguments={"query": "anything"},
        call_id="c1",
    )
    assert result.ok
    assert result.payload == {"results": []}
    assert "no saved artifacts" in result.summary.lower()


@pytest.mark.asyncio
async def test_dispatch_clamps_top_k_above_max() -> None:
    seen: dict[str, int] = {}

    async def handler(user_id, query, top_k):
        seen["top_k"] = top_k
        return []

    await dispatch_recall_artifacts(
        handler,
        user_id="u",
        arguments={"query": "q", "top_k": 999},
        call_id="c",
    )
    assert seen["top_k"] == MAX_TOP_K


@pytest.mark.asyncio
async def test_dispatch_rejects_empty_query() -> None:
    async def handler(user_id, query, top_k):
        raise AssertionError("handler must not run on bad input")

    result = await dispatch_recall_artifacts(
        handler,
        user_id="u",
        arguments={"query": "   "},
        call_id="c",
    )
    assert not result.ok
    assert "non-empty" in result.payload["error"]


@pytest.mark.asyncio
async def test_dispatch_handler_exception_becomes_error_result() -> None:
    async def handler(user_id, query, top_k):
        raise RuntimeError("backend unavailable")

    result = await dispatch_recall_artifacts(
        handler,
        user_id="u",
        arguments={"query": "q"},
        call_id="c",
    )
    assert not result.ok
    assert "backend unavailable" in result.payload["error"]
