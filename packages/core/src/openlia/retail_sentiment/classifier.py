"""LLM-backed batch classifier for Retail Sentiment.

One LLM call per batch (default 30 items). On JSON/schema violation we
retry once; on a second failure we fall back to marking every item
neutral so the pipeline still produces a snapshot. Every call emits a
`ClassificationAudit` record -- the server wraps this and persists one
`rs_classification_log` row per batch.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Sequence

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import LLMRequest, Message
from openlia.retail_sentiment.schemas import (
    BatchClassifyResult,
    ClassificationAudit,
    ClassificationLabel,
    ClassifiedItem,
    RawSocialPost,
)

DEPARTMENT_ID = "retail_sentiment"
DEFAULT_BATCH_SIZE = 30


def _neutral_items(posts: Sequence[RawSocialPost]) -> list[ClassifiedItem]:
    return [
        ClassifiedItem(
            id=p.id,
            classification=ClassificationLabel.NEUTRAL,
            confidence=0.5,
            key_phrases=[],
        )
        for p in posts
    ]


def _parse_response(raw_text: str, posts: Sequence[RawSocialPost]) -> list[ClassifiedItem]:
    """Parse the model's JSON response into ClassifiedItems. Raises
    `ValueError` on any schema violation so the caller can retry or fall
    back."""
    data = json.loads(raw_text)
    if isinstance(data, dict):
        items_raw = data.get("items")
    else:
        items_raw = data
    if not isinstance(items_raw, list):
        raise ValueError(f"expected JSON array or {{items: [...]}}, got {type(items_raw).__name__}")
    if len(items_raw) != len(posts):
        raise ValueError(f"expected {len(posts)} items, got {len(items_raw)}")

    by_id = {p.id: p for p in posts}
    results: list[ClassifiedItem] = []
    for idx, entry in enumerate(items_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"item {idx} is not an object")
        item_id = entry.get("id")
        if item_id not in by_id:
            raise ValueError(f"item {idx} has unknown id {item_id!r}")
        label_raw = entry.get("classification")
        try:
            label = ClassificationLabel(label_raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"item {idx} has bad classification {label_raw!r}") from exc
        confidence = entry.get("confidence")
        if not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0:
            raise ValueError(f"item {idx} has bad confidence {confidence!r}")
        key_phrases = entry.get("key_phrases") or []
        if not isinstance(key_phrases, list):
            raise ValueError(f"item {idx} key_phrases must be a list")
        results.append(
            ClassifiedItem(
                id=str(item_id),
                classification=label,
                confidence=float(confidence),
                key_phrases=[str(p) for p in key_phrases],
            )
        )
    return results


class LlmClassifier:
    """Batch LLM classifier. Async.

    - One LLM call per chunk of up to `batch_size` posts.
    - On JSON/schema failure retries once, then falls back to neutral.
    - Emits one ClassificationAudit per LLM call (success or failure).
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        prompts: PromptLoader,
        model_ref: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        department_id: str = DEPARTMENT_ID,
    ) -> None:
        self._provider = provider
        self._prompts = prompts
        self._model_ref = model_ref
        self._batch_size = max(1, batch_size)
        self._department_id = department_id

    async def classify_batch(
        self, *, ticker: str, posts: Sequence[RawSocialPost]
    ) -> BatchClassifyResult:
        if not posts:
            return BatchClassifyResult(items=[])

        all_items: list[ClassifiedItem] = []
        audits: list[ClassificationAudit] = []
        for chunk_start in range(0, len(posts), self._batch_size):
            chunk = list(posts[chunk_start : chunk_start + self._batch_size])
            chunk_items, audit = await self._classify_chunk(ticker=ticker, posts=chunk)
            all_items.extend(chunk_items)
            audits.append(audit)
        return BatchClassifyResult(items=all_items, audits=audits)

    async def _classify_chunk(
        self, *, ticker: str, posts: Sequence[RawSocialPost]
    ) -> tuple[list[ClassifiedItem], ClassificationAudit]:
        batch_id = str(uuid.uuid4())
        system = self._prompts.render(self._department_id, "batch.classify_batch.system")
        items_json = json.dumps(
            [
                {
                    "id": p.id,
                    "source": p.source,
                    "text": p.text,
                }
                for p in posts
            ]
        )
        user = self._prompts.render(
            self._department_id,
            "batch.classify_batch.user",
            ticker=ticker,
            items=list(posts),
            items_json=items_json,
        )

        start = time.perf_counter()
        last_error: str | None = None
        prompt_tokens = 0
        completion_tokens = 0

        for _attempt in range(2):
            try:
                response = await self._provider.generate(
                    LLMRequest(
                        messages=[Message(role="user", content=user)],
                        system=system,
                        max_tokens=2048,
                        temperature=0.0,
                    )
                )
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc!s}"
                continue

            prompt_tokens = response.input_tokens
            completion_tokens = response.output_tokens
            try:
                items = _parse_response(response.text, posts)
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = f"{type(exc).__name__}: {exc!s}"
                continue
            latency_ms = int((time.perf_counter() - start) * 1000)
            return items, ClassificationAudit(
                batch_id=batch_id,
                ticker=ticker,
                model_ref=self._model_ref,
                item_count=len(posts),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                error=None,
            )

        # Both attempts failed -- fall back to neutral classification so
        # the pipeline still produces a snapshot. The audit captures the
        # last error so the failure is visible in `rs_classification_log`.
        latency_ms = int((time.perf_counter() - start) * 1000)
        audit = ClassificationAudit(
            batch_id=batch_id,
            ticker=ticker,
            model_ref=self._model_ref,
            item_count=len(posts),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            error=last_error or "classification failed",
        )
        return _neutral_items(posts), audit
