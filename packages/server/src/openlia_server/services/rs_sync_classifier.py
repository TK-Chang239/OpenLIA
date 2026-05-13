"""Sync adapter wrapping the async `LlmClassifier` so `RsRunner`'s sync
pipeline can use it.

`RsRunner` and its `/run` route are sync; the core `LlmClassifier` is
async because provider adapters are async. FastAPI runs sync route
handlers in a threadpool, so calling `asyncio.run()` here is safe.

`RefreshingSyncLlmClassifier` resolves the configured LLM model per
call (fresh DB session + registry), mirroring `RefreshingReportRunner`.
If no model is configured for the Retail Sentiment department it falls
back to a neutral result so the pipeline still produces a snapshot.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from openlia.llm.adapters import build_adapter
from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.resolver import resolve
from openlia.llm.runtime.prompts import PromptLoader
from openlia.retail_sentiment.classifier import DEPARTMENT_ID, LlmClassifier
from openlia.retail_sentiment.schemas import (
    BatchClassifyResult,
    ClassificationLabel,
    ClassifiedItem,
    RawSocialPost,
)
from sqlalchemy.orm import Session as DBSession

from openlia_server.services.llm_registry import SQLModelRegistry


def _neutral_result(posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
    items = [
        ClassifiedItem(
            id=p.id,
            classification=ClassificationLabel.NEUTRAL,
            confidence=0.5,
            key_phrases=[],
        )
        for p in posts
    ]
    return BatchClassifyResult(items=items, audits=[])


class SyncLlmClassifier:
    """Matches `rs_runner._Classifier`: sync `classify_batch`.

    Kept for tests that pass a pre-built `LlmClassifier` directly.
    """

    def __init__(self, *, llm_classifier: LlmClassifier) -> None:
        self._llm = llm_classifier

    def classify_batch(self, *, ticker: str, posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
        import asyncio

        return asyncio.run(self._llm.classify_batch(ticker=ticker, posts=posts))


class RefreshingSyncLlmClassifier:
    """Resolves + builds an `LlmClassifier` per call; falls back to neutral
    when no model is configured for the Retail Sentiment department."""

    def __init__(
        self,
        *,
        db_session_factory: Callable[[], DBSession],
        prompts: PromptLoader | None = None,
    ) -> None:
        self._factory = db_session_factory
        self._prompts = prompts or PromptLoader()

    def classify_batch(self, *, ticker: str, posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
        if not posts:
            return BatchClassifyResult(items=[], audits=[])

        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            try:
                resolved = resolve(
                    department_id=DEPARTMENT_ID,
                    registry=registry,
                    user_id=None,
                )
            except ModelNotConfiguredError:
                return _neutral_result(posts)

            provider = build_adapter(
                kind=resolved.provider_kind,
                credentials=resolved.credentials,
                model=resolved.model_ref,
                capabilities=resolved.capabilities,
            )
            classifier = LlmClassifier(
                provider=provider,
                prompts=self._prompts,
                model_ref=resolved.model_ref,
            )
        finally:
            db.close()

        import asyncio

        return asyncio.run(classifier.classify_batch(ticker=ticker, posts=posts))
