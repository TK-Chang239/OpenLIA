"""Insights tab narrative synthesis.

Given a `MetricSnapshot` plus the active `SignalAlert`s for a single
ticker, emits a 2-4 sentence plain-text summary via the configured
LLM provider. Returns `None` when the provider is unavailable or
errors out (graceful degrade per spec).
"""

from __future__ import annotations

from collections.abc import Sequence

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import LLMRequest, Message
from openlia.retail_sentiment.schemas import MetricSnapshot, SignalAlert

DEPARTMENT_ID = "retail_sentiment_insights"


async def synthesize_narrative(
    snapshot: MetricSnapshot,
    signals: Sequence[SignalAlert],
    *,
    provider: LLMProvider,
    prompts: PromptLoader,
) -> str | None:
    """Render the narrative-synthesis prompt + call the provider.
    Returns the trimmed prose, or `None` on any provider error."""
    try:
        system = prompts.render(DEPARTMENT_ID, "narrative.synthesize.system")
        user = prompts.render(
            DEPARTMENT_ID,
            "narrative.synthesize.user",
            ticker=snapshot.ticker,
            captured_at=snapshot.captured_at.isoformat(),
            sentiment_score=f"{snapshot.sentiment_score:.3f}",
            buzz_volume=f"{snapshot.buzz_volume:.3f}",
            sentiment_momentum=f"{snapshot.sentiment_momentum:.3f}",
            bull_bear_ratio=f"{snapshot.bull_bear_ratio:.3f}",
            buzz_sentiment_divergence=f"{snapshot.buzz_sentiment_divergence:.3f}",
            cross_source_agreement=f"{snapshot.cross_source_agreement:.3f}",
            signals=[
                {
                    "severity": s.severity,
                    "metric_id": s.metric_id,
                    "message": s.message,
                    "value": f"{s.value:.3f}",
                }
                for s in signals
            ],
        )
    except Exception:
        return None

    try:
        response = await provider.generate(
            LLMRequest(
                messages=[Message(role="user", content=user)],
                system=system,
                max_tokens=512,
                temperature=0.3,
            )
        )
    except Exception:
        return None

    text = (response.text or "").strip()
    return text or None
