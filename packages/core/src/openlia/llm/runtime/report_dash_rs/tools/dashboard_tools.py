"""Output + quant tools for report_dash_rs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from ...report_dash_mr.tools.dashboard_tools import build_emit_dashboard_tool  # noqa: F401
from ...report_v2_3.research import ResearchTool, ToolDescriptor, ToolExecutionError, ToolResult
from ...report_v2_3.schemas import ComputedSource
from ..quant import RetailSentimentInputs, classify_retail_sentiment
from ..schemas import RetailSentimentData

PAYLOAD_MODEL_BY_SLUG: dict[str, type[BaseModel]] = {"retail_sentiment": RetailSentimentData}


def implemented_dashboard_slugs() -> frozenset[str]:
    return frozenset(PAYLOAD_MODEL_BY_SLUG)


def build_classify_retail_sentiment_tool() -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            out = classify_retail_sentiment(
                RetailSentimentInputs(
                    bullish=int(args["bullish"]),
                    bearish=int(args["bearish"]),
                    neutral=int(args["neutral"]),
                    buzz_level=str(args["buzz_level"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "classify_retail_sentiment requires integer bullish, bearish, neutral "
                f"and a buzz_level of low|elevated|high. {exc}"
            ) from exc
        return ToolResult(
            payload={
                "sentiment_score": out.sentiment_score,
                "direction": out.direction,
                "bull_pct": out.bull_pct,
                "bear_pct": out.bear_pct,
                "signals": out.signals,
            },
            provenance=ComputedSource(
                method="classify_retail_sentiment", derived_from=["(counts)"]
            ),
            summary=f"score={out.sentiment_score} direction={out.direction}",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="classify_retail_sentiment",
            description=(
                "Deterministic retail-sentiment score + signal flags from the counts of "
                "bullish / bearish / neutral items you gathered, plus your qualitative "
                "buzz_level (low|elevated|high). Use the returned sentiment_score, direction, "
                "bull_pct, bear_pct, and signals verbatim in the payload."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "bullish": {"type": "integer", "minimum": 0},
                    "bearish": {"type": "integer", "minimum": 0},
                    "neutral": {"type": "integer", "minimum": 0},
                    "buzz_level": {"type": "string", "enum": ["low", "elevated", "high"]},
                },
                "required": ["bullish", "bearish", "neutral", "buzz_level"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


CLASSIFY_TOOL_BY_SLUG: dict[str, list[Callable[[], ResearchTool]]] = {
    "retail_sentiment": [build_classify_retail_sentiment_tool],
}
