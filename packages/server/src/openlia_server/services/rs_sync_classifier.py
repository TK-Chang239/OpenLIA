"""Sync adapter wrapping the async `LlmClassifier` so `RsRunner`'s sync
pipeline can use it.

`RsRunner` and its `/run` route are sync; the core `LlmClassifier` is
async because provider adapters are async. FastAPI runs sync route
handlers in a threadpool, so calling `asyncio.run()` here is safe.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from openlia.retail_sentiment.classifier import LlmClassifier
from openlia.retail_sentiment.schemas import BatchClassifyResult, RawSocialPost


class SyncLlmClassifier:
    """Matches `rs_runner._Classifier`: sync `classify_batch`."""

    def __init__(self, *, llm_classifier: LlmClassifier) -> None:
        self._llm = llm_classifier

    def classify_batch(self, *, ticker: str, posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
        return asyncio.run(self._llm.classify_batch(ticker=ticker, posts=posts))
