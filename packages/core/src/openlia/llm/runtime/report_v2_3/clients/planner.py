"""Client protocol for the PLAN stage.

A `PlannerClient` consumes the raw prompt + the CLARIFY assumptions and
returns an `Outline` whose sections each enumerate their `data_needs`.
That `data_needs` list becomes RESEARCH's targeted work queue, so a good
plan is what makes research directed instead of speculative — planning
quality compounds downstream.

The real implementation calls the Anthropic / OpenAI SDK with the
planner prompt; tests inject `FakePlannerClient` with a canned outline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import ClarifyResult, Language, Outline, ReportType


@dataclass(slots=True)
class PlannerRequest:
    """Input passed to the planner LLM call."""

    raw_prompt: str
    language: Language
    report_type: ReportType
    tickers: list[str]
    clarify_result: ClarifyResult | None = None


class PlannerClient(Protocol):
    def plan(self, request: PlannerRequest) -> Outline: ...


class FakePlannerClient(PlannerClient):
    """Test fake. Provide either a fixed `result` or a `responder`."""

    def __init__(
        self,
        result: Outline | None = None,
        responder: Callable[[PlannerRequest], Outline] | None = None,
    ) -> None:
        if (result is None) == (responder is None):
            raise ValueError("Provide exactly one of `result` or `responder`.")
        self._result = result
        self._responder = responder
        self.calls: list[PlannerRequest] = []

    def plan(self, request: PlannerRequest) -> Outline:
        self.calls.append(request)
        if self._responder is not None:
            return self._responder(request)
        assert self._result is not None
        return self._result
