"""Unit tests for LlmClassifier.

A `_FakeProvider` substitutes for a real LLM adapter — each test scripts
the exact response(s) it wants back. The real `PromptLoader` is used so
the tests also validate the `batch.classify_batch.*` prompt slots exist
and render."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import LLMRequest, LLMResponse
from openlia.retail_sentiment.classifier import (
    LlmClassifier,
    _parse_response,
)
from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    RawSocialPost,
)


def _post(id_: str, text: str = "up!") -> RawSocialPost:
    return RawSocialPost(
        id=id_,
        ticker="AAPL",
        source="twitter",
        text=text,
        engagement={},
        created_at=datetime.now(UTC),
    )


class _FakeProvider:
    """Async-scripted LLMProvider stand-in. Each `responses` entry is
    either an LLMResponse to return or an Exception to raise."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def stream(self, *args: Any, **kwargs: Any):
        raise NotImplementedError


def _ok(items: list[dict], *, prompt_tokens: int = 10, completion_tokens: int = 20) -> LLMResponse:
    return LLMResponse(
        text=json.dumps({"items": items}),
        finish_reason="stop",
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
    )


@pytest.mark.asyncio
async def test_classify_batch_happy_path() -> None:
    posts = [_post("p1"), _post("p2")]
    provider = _FakeProvider(
        responses=[
            _ok(
                [
                    {
                        "id": "p1",
                        "classification": "bullish",
                        "confidence": 0.8,
                        "key_phrases": ["rocket"],
                    },
                    {
                        "id": "p2",
                        "classification": "bearish",
                        "confidence": 0.65,
                        "key_phrases": [],
                    },
                ]
            )
        ]
    )
    classifier = LlmClassifier(
        provider=provider,
        prompts=PromptLoader(),
        model_ref="gpt-5.4",
    )

    result = await classifier.classify_batch(ticker="AAPL", posts=posts)

    assert [it.id for it in result.items] == ["p1", "p2"]
    assert result.items[0].classification is ClassificationLabel.BULLISH
    assert result.items[1].classification is ClassificationLabel.BEARISH
    assert len(result.audits) == 1
    audit = result.audits[0]
    assert audit.ticker == "AAPL"
    assert audit.model_ref == "gpt-5.4"
    assert audit.item_count == 2
    assert audit.prompt_tokens == 10
    assert audit.completion_tokens == 20
    assert audit.error is None


@pytest.mark.asyncio
async def test_classify_batch_retries_once_then_succeeds() -> None:
    posts = [_post("p1")]
    provider = _FakeProvider(
        responses=[
            LLMResponse(
                text="not json at all",
                finish_reason="stop",
                input_tokens=5,
                output_tokens=5,
            ),
            _ok(
                [{"id": "p1", "classification": "neutral", "confidence": 0.5, "key_phrases": []}],
                prompt_tokens=7,
                completion_tokens=9,
            ),
        ]
    )
    classifier = LlmClassifier(
        provider=provider,
        prompts=PromptLoader(),
        model_ref="gpt-5.4",
    )

    result = await classifier.classify_batch(ticker="AAPL", posts=posts)

    assert len(provider.calls) == 2  # one retry
    assert result.items[0].classification is ClassificationLabel.NEUTRAL
    assert result.audits[0].error is None
    assert result.audits[0].prompt_tokens == 7  # tokens from the successful attempt


@pytest.mark.asyncio
async def test_classify_batch_falls_back_to_neutral_after_two_failures() -> None:
    posts = [_post("p1"), _post("p2")]
    provider = _FakeProvider(
        responses=[
            LLMResponse(
                text="not json at all",
                finish_reason="stop",
                input_tokens=5,
                output_tokens=5,
            ),
            LLMResponse(
                text=json.dumps({"items": [{"id": "wrong", "classification": "x"}]}),
                finish_reason="stop",
                input_tokens=5,
                output_tokens=5,
            ),
        ]
    )
    classifier = LlmClassifier(
        provider=provider,
        prompts=PromptLoader(),
        model_ref="gpt-5.4",
    )

    result = await classifier.classify_batch(ticker="AAPL", posts=posts)

    assert len(provider.calls) == 2
    # All items fall back to neutral.
    assert all(it.classification is ClassificationLabel.NEUTRAL for it in result.items)
    assert [it.id for it in result.items] == ["p1", "p2"]
    # Audit carries the last error so the failure is visible.
    assert result.audits[0].error is not None
    assert "expected 2 items" in result.audits[0].error


@pytest.mark.asyncio
async def test_classify_batch_chunks_at_batch_size() -> None:
    posts = [_post(f"p{i}") for i in range(5)]
    provider = _FakeProvider(
        responses=[
            _ok(
                [
                    {
                        "id": f"p{i}",
                        "classification": "neutral",
                        "confidence": 0.5,
                        "key_phrases": [],
                    }
                    for i in range(2)
                ]
            ),
            _ok(
                [
                    {
                        "id": f"p{i}",
                        "classification": "neutral",
                        "confidence": 0.5,
                        "key_phrases": [],
                    }
                    for i in range(2, 4)
                ]
            ),
            _ok(
                [
                    {
                        "id": "p4",
                        "classification": "neutral",
                        "confidence": 0.5,
                        "key_phrases": [],
                    }
                ]
            ),
        ]
    )
    classifier = LlmClassifier(
        provider=provider,
        prompts=PromptLoader(),
        model_ref="gpt-5.4",
        batch_size=2,
    )

    result = await classifier.classify_batch(ticker="AAPL", posts=posts)

    assert len(result.items) == 5
    assert len(result.audits) == 3  # chunks of 2, 2, 1


@pytest.mark.asyncio
async def test_classify_batch_empty_posts_skips_llm() -> None:
    provider = _FakeProvider(responses=[])
    classifier = LlmClassifier(
        provider=provider,
        prompts=PromptLoader(),
        model_ref="gpt-5.4",
    )

    result = await classifier.classify_batch(ticker="AAPL", posts=[])

    assert result.items == []
    assert result.audits == []
    assert provider.calls == []


def test_parse_response_accepts_bare_array() -> None:
    posts = [_post("p1")]
    payload = json.dumps(
        [{"id": "p1", "classification": "bullish", "confidence": 0.9, "key_phrases": []}]
    )
    items = _parse_response(payload, posts)
    assert len(items) == 1
    assert items[0].classification is ClassificationLabel.BULLISH


def test_parse_response_rejects_length_mismatch() -> None:
    posts = [_post("p1"), _post("p2")]
    payload = json.dumps({"items": [{"id": "p1", "classification": "bullish", "confidence": 0.9}]})
    with pytest.raises(ValueError, match="expected 2 items"):
        _parse_response(payload, posts)
