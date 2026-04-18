from __future__ import annotations

from openlia.llm.types import ModelTier

DEPARTMENT_DEFAULT_TIERS: dict[str, ModelTier] = {
    "secretary": ModelTier.EVERYDAY,
    "equity_research": ModelTier.THINKING,
    "earnings_update": ModelTier.EVERYDAY,
    "morning_briefing": ModelTier.EVERYDAY,
    "retail_sentiment": ModelTier.QUICK,
    "macro_research": ModelTier.THINKING,
    "panic_thermometer": ModelTier.QUICK,
}


DEPARTMENT_TIER_REASONS: dict[str, str] = {
    "secretary": "Conversational Q&A needs a balance of speed and reasoning.",
    "equity_research": "Multi-section report drafting with heavy reasoning over fundamentals.",
    "earnings_update": "Standardized scorecard analysis; benefits from a solid all-rounder.",
    "morning_briefing": "News summarization with light reasoning; speed matters.",
    "retail_sentiment": "High-volume classification of social posts; batched micro-tasks.",
    "macro_research": "Framework-driven analysis with long context and deep reasoning.",
    "panic_thermometer": "Real-time indicator scoring; cheap and fast.",
}
