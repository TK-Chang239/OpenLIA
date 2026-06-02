"""Tests for the provider batch-transport abstraction."""

from __future__ import annotations

from openlia.llm.batch_transport import (
    BatchRequestItem,
    BatchResultItem,
    BatchStatus,
    supports_batch,
)
from openlia.llm.types import LLMRequest, LLMResponse, Message


def test_supports_batch_true_for_openai_and_anthropic():
    assert supports_batch("openai", "gpt-5.4-2026-03-05") is True
    assert supports_batch("anthropic", "claude-sonnet-4-6") is True


def test_supports_batch_false_for_others():
    assert supports_batch("openrouter", "anything") is False
    assert supports_batch("ollama", "llama3") is False
    assert supports_batch("gemini", "gemini-2.5-pro") is False
    assert supports_batch("openai_responses", "gpt-5.4") is False


def test_batch_request_item_holds_custom_id_and_request():
    req = LLMRequest(messages=[Message(role="user", content="hi")])
    item = BatchRequestItem(custom_id="r1", request=req)
    assert item.custom_id == "r1"
    assert item.request is req


def test_batch_result_item_ok_and_error_shapes():
    resp = LLMResponse(text="ok", finish_reason="stop", input_tokens=1, output_tokens=1)
    ok = BatchResultItem(custom_id="r1", response=resp, error=None)
    err = BatchResultItem(custom_id="r2", response=None, error="boom")
    assert ok.response is resp and ok.error is None
    assert err.response is None and err.error == "boom"


def test_batch_status_members():
    assert BatchStatus.IN_PROGRESS == "in_progress"
    assert BatchStatus.COMPLETED == "completed"
    assert BatchStatus.FAILED == "failed"
    assert BatchStatus.EXPIRED == "expired"
