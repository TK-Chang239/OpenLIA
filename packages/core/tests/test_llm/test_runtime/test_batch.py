from __future__ import annotations

import asyncio
import json
from pathlib import Path
from textwrap import dedent
from typing import Literal

import pytest
from _fakes import FakeProvider, FakeProviderScript
from openlia.llm.exceptions import ContextLengthError, TierNotConfiguredError
from openlia.llm.runtime.batch import BatchRunner
from openlia.llm.runtime.messages import BatchItem
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import (
    Capabilities,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
)
from pydantic import BaseModel

pytestmark = pytest.mark.asyncio


class SentimentResult(BaseModel):
    sentiment: Literal["bullish", "bearish", "neutral"]
    confidence: float


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    shared = root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("return json.\n")
    (root / "retail_sentiment.yaml").write_text(
        dedent(
            """\
            batch:
              classify_sentiment:
                system: classify.
                user: |
                  Ticker: {{ ticker }}
                  Text: {{ text }}
            """
        )
    )
    return root


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        tier=ModelTier.QUICK,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=False, structured_output=True),
        overrides={},
    )


class _Registry:
    def get_department_tier_override(self, department_id: str):
        return None

    def get_user_preference(self, user_id, tier):
        return None

    def get_tier_default(self, tier):
        return None

    def get_any_in_tier(self, tier):
        return None


def _always(resolved):
    def _r(*, department_id, user_id, registry, tier_override=None):
        return resolved

    return _r


def _raises(exc):
    def _r(*, department_id, user_id, registry, tier_override=None):
        raise exc

    return _r


async def test_batch_runs_all_items_ok(prompts_root: Path) -> None:
    def provider_factory(resolved):
        return FakeProvider(
            script=FakeProviderScript(
                turns=[
                    ("final_json", json.dumps({"sentiment": "bullish", "confidence": 0.9})),
                    ("final_json", json.dumps({"sentiment": "bearish", "confidence": 0.8})),
                    ("final_json", json.dumps({"sentiment": "neutral", "confidence": 0.5})),
                ]
            )
        )

    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=provider_factory,
    )
    items = [
        BatchItem(id=f"p{i}", context={"ticker": "AAPL", "text": t})
        for i, t in enumerate(["to the moon", "drop the bag", "meh"])
    ]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=2,
    )
    assert [r.id for r in results] == ["p0", "p1", "p2"]
    assert all(r.ok for r in results)
    assert results[0].data["sentiment"] == "bullish"
    assert results[1].data["sentiment"] == "bearish"


async def test_batch_surfaces_per_item_failure_without_sinking_batch(
    prompts_root: Path,
) -> None:
    class _PartiallyFailingProvider(FakeProvider):
        def __init__(self):
            super().__init__(
                script=FakeProviderScript(
                    turns=[
                        ("final_json", json.dumps({"sentiment": "bullish", "confidence": 0.9})),
                        ("final_json", json.dumps({"sentiment": "neutral", "confidence": 0.5})),
                    ]
                )
            )
            self._calls = 0

        async def generate(self, request):
            self._calls += 1
            if self._calls == 2:
                raise ContextLengthError("too long", limit=1000)
            return await super().generate(request)

    provider = _PartiallyFailingProvider()
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
    )
    items = [
        BatchItem(id="ok", context={"ticker": "AAPL", "text": "a"}),
        BatchItem(id="bad", context={"ticker": "AAPL", "text": "b"}),
        BatchItem(id="ok2", context={"ticker": "AAPL", "text": "c"}),
    ]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=1,
    )
    by_id = {r.id: r for r in results}
    assert by_id["ok"].ok is True
    assert by_id["bad"].ok is False
    assert "ContextLengthError" in by_id["bad"].error
    assert by_id["ok2"].ok is True


async def test_batch_tier_not_configured_fails_every_item(prompts_root: Path) -> None:
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_raises(TierNotConfiguredError("quick")),
        registry=_Registry(),
        provider_factory=lambda r: FakeProvider(),
    )
    items = [
        BatchItem(id="p0", context={"ticker": "AAPL", "text": "a"}),
        BatchItem(id="p1", context={"ticker": "AAPL", "text": "b"}),
    ]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=2,
    )
    assert all(r.ok is False for r in results)
    assert all("TierNotConfiguredError" in r.error for r in results)


async def test_batch_concurrency_is_bounded(prompts_root: Path) -> None:
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    class _Counting(FakeProvider):
        def __init__(self):
            super().__init__(
                script=FakeProviderScript(
                    turns=[("final_json", json.dumps({"sentiment": "neutral", "confidence": 0.1}))]
                    * 10
                )
            )

        async def generate(self, request):
            nonlocal in_flight, peak
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            try:
                await asyncio.sleep(0.02)
                return await super().generate(request)
            finally:
                async with lock:
                    in_flight -= 1

    provider = _Counting()
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
    )
    items = [BatchItem(id=f"p{i}", context={"ticker": "AAPL", "text": f"t{i}"}) for i in range(10)]
    await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=3,
    )
    assert peak <= 3


async def test_batch_rejects_invalid_json_as_per_item_error(prompts_root: Path) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", "not json at all")]))
    runner = BatchRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
    )
    items = [BatchItem(id="p0", context={"ticker": "AAPL", "text": "a"})]
    results = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=SentimentResult,
        concurrency=1,
    )
    assert results[0].ok is False
    assert "JSON" in results[0].error or "validation" in results[0].error.lower()
